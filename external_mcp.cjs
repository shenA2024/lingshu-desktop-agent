/* Tool-only relay using the exact MCP client shipped by the supported Harness. */
'use strict';
const {createRequire}=require('module');
const readline=require('readline');
const version=require('fs').readFileSync(require('path').join(__dirname,'version.py'),'utf8').match(/VERSION\s*=\s*['"]([0-9.]+)['"]/)[1];
const local=createRequire(process.env.LINGSHU_DSH_CLI);
const {Client,StreamableHTTPClientTransport}=local('@modelcontextprotocol/client');
const {StdioClientTransport}=local('@modelcontextprotocol/client/stdio');
let client,transport;
const calls=new Map();
const send=value=>process.stdout.write(JSON.stringify(value)+'\n');
async function connect(spec){
  client=new Client({name:'lingshu-tools',version},{capabilities:{}});
  const env=Object.fromEntries(Object.entries(process.env).filter(([key])=>!(/KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|^DSH_|^MDCG_|^LINGSHU_/i.test(key))));
  transport=spec.transport==='stdio'?new StdioClientTransport({command:spec.command,args:spec.args,cwd:spec.cwd||undefined,env:{...env,...spec.env},stderr:'ignore'}):new StreamableHTTPClientTransport(new URL(spec.url),{requestInit:{headers:spec.headers}});
  await client.connect(transport);
}
async function listTools(){return client.getServerCapabilities()?.tools?await client.listTools(undefined,{cacheMode:'refresh'}):{tools:[]};}
async function finish(){try{await client?.close();}catch{} }
async function main(){
  if(process.argv.includes('--probe')){
    let input='';for await(const chunk of process.stdin)input+=chunk;
    try{await connect(JSON.parse(input));const result=await listTools();send({ok:true,server:client.getServerVersion(),tools:result.tools.map(t=>({name:t.name,description:t.description||''}))});}
    catch{send({ok:false});process.exitCode=1;}finally{await finish();}return;
  }
  const spec=JSON.parse(process.env.LINGSHU_MCP_SPEC);delete process.env.LINGSHU_MCP_SPEC;
  await connect(spec);
  const lines=readline.createInterface({input:process.stdin,crlfDelay:Infinity});
  lines.on('line',async line=>{
    let request;try{request=JSON.parse(line);}catch{return;}
    if(request.method==='notifications/cancelled'){calls.get(request.params?.requestId)?.abort();return;}
    if(request.id===undefined)return;
    const controller=new AbortController();calls.set(request.id,controller);
    try{
      let result;
      if(request.method==='initialize')result={protocolVersion:request.params.protocolVersion,capabilities:{tools:{}},serverInfo:{name:'lingshu-tool-relay',version}};
      else if(request.method==='ping')result={};
      else if(request.method==='tools/list')result=await listTools();
      else if(request.method==='tools/call')result=await client.callTool(request.params,{signal:controller.signal,timeout:60000});
      else {send({jsonrpc:'2.0',id:request.id,error:{code:-32601,message:'Method not supported'}});return;}
      send({jsonrpc:'2.0',id:request.id,result});
    }catch{send({jsonrpc:'2.0',id:request.id,error:{code:-32000,message:'External MCP request failed. Check the connection.'}});}
    finally{calls.delete(request.id);}
  });
  lines.on('close',async()=>{for(const controller of calls.values())controller.abort();await finish();});
}
main().catch(async()=>{await finish();process.exitCode=1;});
