/**
 * 文件功能：
 * - 解包 Axios 客户端拦截器返回的统一 API 响应体。
 */

export function readApiData(response) {
  return response?.data ?? null;
}
