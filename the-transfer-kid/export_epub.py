import os, markdown
from ebooklib import epub

for ch_num in range(20, 25):
    src = f'/Users/guziyang/Documents/Novel/the-transfer-kid/chapter-{ch_num}.md'
    dst = f'/Users/guziyang/Desktop/The Transfer kid/chapter-{ch_num}.epub'
    
    with open(src, 'r', encoding='utf-8') as f:
        text = f.read()
        html = markdown.markdown(text, extensions=['extra'])
    
    title_line = text.split('\n')[0].strip().replace('# ', '')
    
    book = epub.EpubBook()
    book.set_identifier(f'transfer-kid-ch{ch_num}')
    book.set_title(f'The Transfer Kid — {title_line}')
    book.set_language('en')
    book.add_author('Author')
    
    style = epub.EpubItem(uid='style', file_name='style/default.css', media_type='text/css',
        content=b'body{font-family:Georgia,serif;line-height:1.8;margin:2em;color:#222}h1{font-size:1.6em;margin-bottom:.5em}p{margin-bottom:.8em;text-indent:0}em{font-style:italic}hr{border:none;border-top:1px solid #ccc;margin:2em 0}')
    book.add_item(style)
    
    ch = epub.EpubHtml(title=title_line, file_name=f'chapter{ch_num}.xhtml', lang='en')
    ch.content = f'<html><body>{html}</body></html>'
    ch.add_item(style)
    book.add_item(ch)
    
    book.toc = [epub.Link(f'chapter{ch_num}.xhtml', title_line, f'ch{ch_num}')]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ['nav', ch]
    
    epub.write_epub(dst, book, {})
    print(f'✅ Done: {dst}')
