from pathlib import Path  # Python自带的文件路径工具。

from langchain_text_splitters import MarkdownHeaderTextSplitter


# __file__是当前knowledge.py的位置。
# parent.parent从services目录回到backend目录。
SOURCE_FILE = (
    Path(__file__).resolve().parent.parent
    / "knowledge_samples"
    / "low-stock-sop-v1.md"
)


def preview_sop_chunks() -> dict:
    # 读取文件文字；utf-8-sig同时兼容带BOM的UTF-8文件。
    text = SOURCE_FILE.read_text(encoding="utf-8-sig")

    # 统一换行，去掉全文开头和结尾的空白。
    text = text.replace("\r\n", "\n").strip()

    if not text:
        raise ValueError("SOP文档内容为空")

    # 按Markdown的一、二级标题划分内容。
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[
            ("#", "title"),
            ("##", "section"),
        ],
        strip_headers=False,  # 每块正文保留自己的标题。
    )

    # split_text接收字符串，返回多个Document对象。
    documents = splitter.split_text(text)

    chunks = []

    # enumerate同时提供序号和当前对象，序号从1开始。
    for index, document in enumerate(documents, start=1):
        chunks.append({
            # 当前样例使用固定文档编号和版本。
            "chunk_id": f"SOP-INVENTORY-001:v1:{index}",
            "content": document.page_content,
            "metadata": {
                **document.metadata,  # 展开工具已经提供的标题信息。
                "document_id": "SOP-INVENTORY-001",
                "version": "v1",
                "source": SOURCE_FILE.name,  # 只返回文件名。
                "section": document.metadata.get(
                    "section", "文档说明"
                ),  # 标题前的说明文字归入“文档说明”。
                "data_source": "synthetic_demo",
            },
        })

    return {
        "document_id": "SOP-INVENTORY-001",
        "version": "v1",
        "chunk_count": len(chunks),
        "chunks": chunks,
    }