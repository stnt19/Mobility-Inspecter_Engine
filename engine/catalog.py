"""Validate source-linked catalog packs before activating them."""
import hashlib
import io
import re
from tools.contract import CLASSES
from .store import finite, validate_box


def validate_catalog(c, pdf):
    if (not isinstance(c, dict) or c.get('schema_version') != 1
            or not isinstance(c.get('rows'), list) or not 1 <= len(c['rows']) <= 20000
            or type(c.get('page_count')) is not int or not 1 <= c['page_count'] <= 3000
            or not re.fullmatch('[a-fA-F0-9]{64}', str(c.get('source_sha256', '')))):
        raise ValueError('카탈로그 형식이 올바르지 않습니다.')
    if hashlib.sha256(pdf).hexdigest() != c['source_sha256'].lower():
        raise ValueError('카탈로그 PDF 체크섬 불일치')
    from pypdf import PdfReader
    if len(PdfReader(io.BytesIO(pdf)).pages) != c['page_count']:
        raise ValueError('PDF 페이지 수 불일치')
    ids = set()
    for r in c['rows']:
        if (not isinstance(r, dict) or not isinstance(r.get('id'), str) or r['id'] in ids
                or not isinstance(r.get('part_number'), str)
                or type(r.get('pdf_page')) is not int or not 1 <= r['pdf_page'] <= c['page_count']
                or not isinstance(r.get('relations'), dict)
                or any(k not in CLASSES or v not in ('primary', 'related') for k, v in r['relations'].items())
                or not isinstance(r.get('diagram_pages'), list)
                or any(type(p) is not int or not 1 <= p <= c['page_count'] for p in r['diagram_pages'])
                or not all(finite(r.get(k)) and r[k] > 0 for k in ('page_width', 'page_height'))):
            raise ValueError('카탈로그 행이 올바르지 않습니다.')
        validate_box(r.get('row_rect'), r['page_width'], r['page_height'])
        ids.add(r['id'])
    return c
