export type BasisLimits = {
  max_documents: number;
  per_document_characters: number;
  max_total_characters: number;
  max_requirements_characters: number;
};
export type BasisCandidate = {
  path: string;
  size: number;
  excerpt_characters?: number;
};
export const defaultBasisLimits: BasisLimits = {
  max_documents: 4,
  per_document_characters: 12000,
  max_total_characters: 24000,
  max_requirements_characters: 12000,
};
export const characters = (text: string) => Array.from(text).length;
export function basisSelection(
  candidates: BasisCandidate[],
  selected: string[],
  requirements: string,
  limits = defaultBasisLimits,
) {
  const byPath = new Map(candidates.map((d) => [d.path, d]));
  const missing = selected.filter((path) => !byPath.has(path));
  const count = selected.length;
  const excerpt = (d: BasisCandidate) =>
    d.excerpt_characters ?? Math.min(d.size, limits.per_document_characters);
  const total = selected.reduce(
    (n, path) => n + (byPath.has(path) ? excerpt(byPath.get(path)!) : 0),
    characters(requirements.trim()),
  );
  const error = missing.length
    ? "仓库依据已变化，请重新选择文档。"
    : count > limits.max_documents
      ? `本次最多选择 ${limits.max_documents} 份依据文档，当前已选 ${count} 份。`
      : new Set(selected).size !== count
        ? "依据文档不能重复选择。"
        : characters(requirements) > limits.max_requirements_characters
          ? `补充需求最多 ${limits.max_requirements_characters.toLocaleString()} 字符。`
          : total > limits.max_total_characters
            ? `依据合计超过 ${limits.max_total_characters.toLocaleString()} 字符，请减少文档或补充需求。`
            : !count && !requirements.trim()
              ? "请选择独立依据文档，或补充需求。"
              : "";
  return {
    count,
    total,
    error,
    canGenerate: !error,
    disabled: (d: BasisCandidate) =>
      !selected.includes(d.path) &&
      (count >= limits.max_documents ||
        total + excerpt(d) > limits.max_total_characters),
  };
}

// Recommendations are explicit selections, never an automatic claim of coverage.
export function recommendedBasis(
  candidates: BasisCandidate[],
  requirements: string,
  limits = defaultBasisLimits,
) {
  const selected: string[] = [];
  for (const candidate of candidates) {
    if (
      !basisSelection(candidates, selected, requirements, limits).disabled(
        candidate,
      )
    )
      selected.push(candidate.path);
  }
  return selected;
}

export function readableApiError(raw: string): string {
  try {
    const body = JSON.parse(raw);
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail))
      return body.detail
        .map((item: any) => {
          const field = item.loc?.[1];
          if (field === "documents" && item.type === "too_long")
            return `本次最多选择 ${item.ctx?.max_length ?? 4} 份依据文档，当前已选 ${item.ctx?.actual_length ?? "过多"} 份。请取消部分选择后再生成。`;
          if (field === "requirements_text" && item.type === "string_too_long")
            return "补充需求过长，请缩小本次验收范围。";
          if (typeof item.msg === "string" && item.type === "value_error")
            return item.msg.replace(/^Value error, /, "");
          return "提交内容不符合要求，请检查文档选择和输入长度。";
        })
        .join("\n");
    return typeof body === "string" ? body : "请求失败，请检查输入后重试。";
  } catch {
    /* The API also returns plain Chinese conflict messages. */
  }
  return raw || "请求失败，请稍后重试。";
}
