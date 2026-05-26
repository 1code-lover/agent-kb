/**
 * 文件功能：
 * - 通用占位页面组件，用于临时承载未实现页面入口。
 */

/**
 * 占位页面组件。
 *
 * 输入：
 * - title(string): 页面标题。
 * - text(string): 页面说明文案。
 *
 * 输出：
 * - JSX.Element: 占位展示内容。
 */
export default function PlaceholderPage({ title, text }) {
  return (
    <section>
      <h2>{title}</h2>
      <p>{text}</p>
    </section>
  );
}
