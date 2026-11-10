from pathlib import Path  # Python自带的文件路径工具。

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from hashlib import sha256


# __file__是当前knowledge.py的位置。
# parent.parent从services目录回到backend目录。
SOURCE_FILE = (
    Path(__file__).resolve().parent.parent
    / "knowledge_samples"
    / "low-stock-sop-v1.md"
)

MAX_DOCUMENT_BYTES = 2 * 1024 * 1024  # 当前文本上传限制为2MiB。


def parser_version_for(filename: str) -> str:
    kind = "markdown" if Path(filename).suffix.lower() == ".md" else "text"
    return kind + "-parent2400-200-child800-120-v2"  # 切分配置变化后重新建立索引。


def parse_uploaded_document(filename: str, content: bytes) -> dict:
    """上传文件解析与分块预览；后续入库功能复用此结果。"""
    # 兼容浏览器传来的Windows路径，元数据只保留文件名。
    source = Path(filename.replace("\\", "/")).name
    suffix = Path(source).suffix.lower()
    if suffix not in {".md", ".txt"}:
        raise ValueError("当前支持.md和.txt文件，请将文档另存为UTF-8文本后上传")
    if len(content) > MAX_DOCUMENT_BYTES:
        raise ValueError("文件超过2MiB限制")
    text = content.decode("utf-8-sig").replace("\r\n", "\n").strip()
    if not text or "\x00" in text:
        raise ValueError("请上传包含有效文字的文档")

    # 内容指纹用于识别相同原文；当前预览阶段使用固定解析版本。
    document_id = sha256(content).hexdigest()
    if suffix == ".md":
        sections = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "title"), ("##", "section")],
            strip_headers=False,
        ).split_text(text)
    else:
        sections = [Document(page_content=text)]
    separators = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
    # 父块保留章节上下文；超长章节继续拆开，控制回答上下文长度。
    parent_documents = RecursiveCharacterTextSplitter(
        chunk_size=2400, chunk_overlap=200, length_function=len,
        separators=separators,
    ).split_documents(sections)
    parents = []
    for index, parent in enumerate(parent_documents, 1):
        parent.metadata["parent_id"] = str(index)  # 编号在当前文档版本内唯一。
        parents.append({"parent_id": str(index), "content": parent.page_content})
    # 子块负责检索；split_documents会把parent_id复制给每个子块。
    documents = RecursiveCharacterTextSplitter(
        chunk_size=800, chunk_overlap=120, length_function=len,
        separators=separators,
    ).split_documents(parent_documents)
    chunks = [{
        "chunk_id": f"{document_id}:v1:{index}",
        "content": document.page_content,
        "metadata": {
            **document.metadata, "source": source,
            "document_id": document_id, "version": "v1",
            "section": document.metadata.get("section", "正文"),
        },
    } for index, document in enumerate(documents, start=1)]
    return {
        "status": "parsed", "indexed": False,
        "document_id": document_id, "filename": source,
        "size_bytes": len(content), "character_count": len(text),
        "chunk_count": len(chunks), "chunks": chunks, "parents": parents,
    }


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
