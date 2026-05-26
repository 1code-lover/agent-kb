/**
 * 文件功能：
 * - 创建并导出统一的 Axios 客户端实例。
 *
 * 执行逻辑：
 * 1. 初始化 baseURL 与超时配置。
 * 2. 统一响应拦截，成功时直接返回 response.data。
 * 3. 统一错误映射，输出可读错误信息给上层调用方。
 */

import axios from "axios";

const client = axios.create({
  baseURL: "http://127.0.0.1:18080",
  timeout: 120000
});

client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    // 统一错误消息格式，避免页面层重复处理后端/网络异常结构差异。
    const message = error?.response?.data?.detail || error.message || "请求失败";
    return Promise.reject(new Error(message));
  }
);

export default client;
