export function CitationAdjustments({ planner }: { planner?: Record<string, any> }) {
  const rows = planner?.citation_adjustments || [];
  if (!rows.length) return null;
  return (
    <details className="console-disclosure">
      <summary>{rows.length} 处引用已按原文定位（仅换行缩进）</summary>
      {rows.map((a: Record<string, any>, i: number) => (
        <section key={i}>
          <p>{a.requirement} · {a.document}:{a.line}</p>
          <p>模型原引用</p><pre>{a.model_quote}</pre>
          <p>定位到的原文</p><pre>{a.quote}</pre>
        </section>
      ))}
    </details>
  );
}
