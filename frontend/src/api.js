function formatDetail(detail) {
  if (!detail) return null;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => item.msg || JSON.stringify(item))
      .join("; ");
  }
  return String(detail);
}

async function request(url, options = {}, timeoutMs = 90000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    if (options.expectBlob) {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(formatDetail(body.detail) || "Request failed");
      }
      return res.blob();
    }
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(formatDetail(body.detail) || "Request failed");
    return body;
  } catch (err) {
    if (err.name === "AbortError") {
      throw new Error("Request timed out — try again or use a smaller sample");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export async function uploadDataset(file) {
  const form = new FormData();
  form.append("file", file);
  return request("/api/datasets", { method: "POST", body: form });
}

export async function setDatasetTarget(datasetId, targetCol) {
  return request(`/api/datasets/${datasetId}/target`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_col: targetCol }),
  });
}

export async function getDatasetScore(datasetId) {
  return request(`/api/datasets/${datasetId}/score`);
}

export async function getDatasetPreview(datasetId, { targetRatio = 1.5, selected } = {}) {
  const params = new URLSearchParams();
  params.set("target_ratio", String(targetRatio));
  if (selected) params.set("selected", selected);
  return request(`/api/datasets/${datasetId}/preview?${params}`, {}, 90000);
}

export async function applyDatasetFix(datasetId, { fix, targetRatio = 1.5 }) {
  return request(`/api/datasets/${datasetId}/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fix, target_ratio: targetRatio }),
  }, 90000);
}

export async function resetDataset(datasetId) {
  return request(`/api/datasets/${datasetId}/reset`, { method: "POST" });
}

export async function downloadDatasetCsv(datasetId) {
  return request(`/api/datasets/${datasetId}/download`, { expectBlob: true });
}
