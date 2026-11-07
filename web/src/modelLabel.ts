type Connection = Record<string, any> | undefined;
export function modelLabel(c: Connection): string {
  if (c?.provider === "chat2api") return "GPT-6 Thinking · High";
  if (c?.provider === "deepseek") return "DeepSeek Flash · High（请求设置）";
  return c?.actual_model || c?.requested_model || "模型辅助设计";
}
export function modelVerification(c: Connection): string {
  if (!c?.verified) return "模型响应待核对";
  return c.verification_scope || "响应型号与强度核对通过";
}
