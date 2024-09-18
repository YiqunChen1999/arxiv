from dataclasses import dataclass
from typing import List
import arxiv

@dataclass
class Result:
    entry_id: str
    updated: str
    published: str
    title: str
    authors: List[str]
    summary: str
    comment: str
    journal_ref: str
    doi: str
    primary_category: str
    categories: List[str]
    pdf_url: str
    links: List[str]
    code_link: str = ""
    chinese_summary: str = ""

    @classmethod
    def from_arxiv_result(cls, arxiv_result: arxiv.Result):
        return cls(
            entry_id=arxiv_result.entry_id,
            updated=arxiv_result.updated.strftime("%Y-%m-%d %H:%M:%S"),
            published=arxiv_result.published.strftime("%Y-%m-%d %H:%M:%S"),
            title=arxiv_result.title,
            authors=[au.name for au in arxiv_result.authors],
            summary=arxiv_result.summary,
            comment=arxiv_result.comment,
            journal_ref=arxiv_result.journal_ref,
            doi=arxiv_result.doi,
            primary_category=arxiv_result.primary_category,
            categories=arxiv_result.categories,
            pdf_url=arxiv_result.pdf_url,
            links=[link.href for link in arxiv_result.links],
        )
