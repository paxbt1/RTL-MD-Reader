const editor = document.querySelector('#source');
const preview = document.querySelector('#preview');
const status = document.querySelector('#save-status');
const count = document.querySelector('#word-count');
const zoomValue = document.querySelector('#zoom-value');
const workspace = document.querySelector('.workspace');
const toggleEditor = document.querySelector('#toggle-editor');
const storageKey = 'persian-markdown-reader:v1';
const sample = `# به خوانشگر مارک‌داون خوش آمدید

اینجا می‌توانید **فارسی** و English را کنار هم بنویسید و نتیجه را همان لحظه در سمت راست بخوانید. متن شما به صورت خودکار در همین مرورگر ذخیره می‌شود.

## یک جدول نمونه

| ویژگی | توضیح | وضعیت |
| :--- | :--- | :--- |
| نمایش فارسی | فونت وزیرمتن و چیدمان راست‌به‌چپ | آماده |
| متن دوزبانه | Persian و English در یک جمله | آماده |
| جدول‌ها | ساختار استاندارد Markdown | آماده |

> برای چپ‌چین کردن یک پاراگراف، نشانگر را داخل آن بگذارید و دکمهٔ چپ‌چین را بزنید.

### نمونهٔ چپ‌چین

::: align-left

This paragraph is left aligned. You can also select a paragraph and change its size.

:::

کدهای کوتاه مثل \`const name = "سلام"\` نیز مرتب نمایش داده می‌شوند.
`;

editor.value = localStorage.getItem(storageKey) ?? sample;
let timer;
let sequence = 0;
let zoom = Number(localStorage.getItem(storageKey + ':zoom')) || 100;
setZoom(zoom);
setEditorCollapsed(localStorage.getItem(storageKey + ':collapsed') === 'true');

function faNumber(n) { return new Intl.NumberFormat('fa-IR').format(n); }
function updateCount() {
  const words = editor.value.trim().match(/[^\s]+/g)?.length || 0;
  count.textContent = `${faNumber(words)} واژه`;
}
async function render() {
  const request = ++sequence;
  try {
    const response = await fetch('/render', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source: editor.value })
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const result = await response.json();
    if (request === sequence) {
      preview.innerHTML = result.html;
      status.textContent = 'ذخیره شد';
    }
  } catch (error) {
    if (request === sequence) status.textContent = 'خطا در نمایش';
    console.error(error);
  }
}
function changed() {
  localStorage.setItem(storageKey, editor.value);
  status.textContent = 'در حال نمایش…';
  updateCount();
  clearTimeout(timer);
  timer = setTimeout(render, 120);
}
editor.addEventListener('input', changed);
updateCount();
render();

function insertText(text, selectStart, selectEnd) {
  const a = editor.selectionStart, b = editor.selectionEnd;
  editor.setRangeText(text, a, b, 'end');
  if (selectStart !== undefined) editor.setSelectionRange(a + selectStart, a + selectEnd);
  editor.focus();
  changed();
}
function surround(left, right, placeholder) {
  const value = editor.value.slice(editor.selectionStart, editor.selectionEnd) || placeholder;
  insertText(left + value + right, left.length, left.length + value.length);
}
function wrapBlock(name) {
  const source = editor.value;
  const start = editor.selectionStart, end = editor.selectionEnd;
  const previous = source.lastIndexOf('\n\n', Math.max(0, start - 1));
  const next = source.indexOf('\n\n', end);
  const a = previous < 0 ? 0 : previous + 2;
  const b = next < 0 ? source.length : next;
  const block = source.slice(a, b).trim();
  if (!block) return;
  const before = source.slice(0, a);
  const after = source.slice(b);
  const replacement = `::: ${name}\n\n${block}\n\n:::`;
  editor.value = before + replacement + after;
  editor.setSelectionRange(a + name.length + 6, a + name.length + 6 + block.length);
  editor.focus();
  changed();
}
document.querySelector('.toolbar').addEventListener('click', event => {
  const button = event.target.closest('button[data-action]');
  if (!button) return;
  const action = button.dataset.action;
  if (action === 'bold') surround('**', '**', 'متن پررنگ');
  else if (action === 'italic') surround('*', '*', 'متن مورب');
  else if (action === 'heading') {
    const at = editor.selectionStart;
    const lineStart = editor.value.lastIndexOf('\n', at - 1) + 1;
    editor.setSelectionRange(lineStart, lineStart);
    insertText('## ');
  }
  else if (action === 'link') surround('[', '](https://example.com)', 'متن پیوند');
  else if (action === 'table') insertText('\n\n| ستون اول | ستون دوم |\n| :--- | :--- |\n| مقدار اول | مقدار دوم |\n\n');
  else wrapBlock(action);
});
editor.addEventListener('keydown', event => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'b') { event.preventDefault(); surround('**', '**', 'متن پررنگ'); }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'i') { event.preventDefault(); surround('*', '*', 'متن مورب'); }
  if (event.key === 'Tab') { event.preventDefault(); insertText('  '); }
});
function setZoom(value) {
  zoom = Math.max(70, Math.min(160, value));
  preview.style.setProperty('--preview-size', `${17 * zoom / 100}px`);
  zoomValue.textContent = `${faNumber(zoom)}٪`;
  localStorage.setItem(storageKey + ':zoom', String(zoom));
}
function setEditorCollapsed(collapsed) {
  workspace.classList.toggle('editor-collapsed', collapsed);
  toggleEditor.textContent = collapsed ? 'نمایش ویرایشگر' : 'جمع کردن ویرایشگر';
  toggleEditor.title = collapsed ? 'باز کردن بخش متن مارک‌داون' : 'جمع کردن بخش متن مارک‌داون';
  toggleEditor.setAttribute('aria-pressed', String(collapsed));
  localStorage.setItem(storageKey + ':collapsed', String(collapsed));
}
toggleEditor.onclick = () => setEditorCollapsed(!workspace.classList.contains('editor-collapsed'));
document.querySelector('#zoom-in').onclick = () => setZoom(zoom + 10);
document.querySelector('#zoom-out').onclick = () => setZoom(zoom - 10);
document.querySelector('#pdf-btn').onclick = async () => {
  clearTimeout(timer);
  await render();
  await document.fonts.ready;
  status.textContent = 'در پنجرهٔ چاپ، «ذخیره به‌صورت PDF» را انتخاب کنید';
  window.print();
};
const fileInput = document.querySelector('#file-input');
document.querySelector('#import-btn').onclick = () => fileInput.click();
fileInput.onchange = async () => {
  const file = fileInput.files?.[0];
  if (!file) return;
  editor.value = await file.text();
  fileInput.value = '';
  changed();
};
document.querySelector('#export-btn').onclick = () => {
  const blob = new Blob([editor.value], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'document.md';
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
