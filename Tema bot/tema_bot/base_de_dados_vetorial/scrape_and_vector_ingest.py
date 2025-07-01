#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import json
from urllib.parse import urljoin
from pathlib import Path

import cloudscraper
from bs4 import BeautifulSoup

BASE_URL     = 'https://ajuda.solides.com.br'
CATEGORY_URL = urljoin(BASE_URL, '/hc/pt-br/categories/25325496607885')

# configura o cloudscraper pra parecer um Chrome real
SCRAPER = cloudscraper.create_scraper(
    browser={ 'custom': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/114.0.5735.199 Safari/537.36'
    )}
)

# pasta de saída
BASE_DIR = Path(__file__).parent
VET_DIR  = BASE_DIR
VET_DIR.mkdir(exist_ok=True)


def get_soup(url):
    resp = SCRAPER.get(url, timeout=10)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, 'html.parser')


def collect_sections_and_direct_articles():
    """
    Agora varre todas as <ul class="article-list"> da página de categoria,
    capturando seções (links contendo '/sections/') e artigos diretos.
    """
    soup = get_soup(CATEGORY_URL)
    secs, arts = [], []

    # pega TODAS as listas de artigos (RH, Benefícios, Academy…)
    for ul in soup.find_all('ul', class_='article-list'):
        for li in ul.find_all('li', class_='article-list-item'):
            a = li.find('a', class_='article-list-item__link')
            href = urljoin(BASE_URL, a['href'])
            title = a.get_text(strip=True)

            # separa seções de artigos diretos
            if '/sections/' in a['href']:
                secs.append({'title': title, 'url': href})
            elif '/articles/' in a['href']:
                arts.append({'title': title, 'url': href})

    return secs, arts


def collect_articles_from_sections(secs, seen):
    new = []
    for sec in secs:
        print(f" ↳ entrando em seção: {sec['title']}")
        soup = get_soup(sec['url'])
        ul   = soup.find('ul', class_='article-list')
        if not ul:
            continue
        for li in ul.find_all('li', class_='article-list-item'):
            a = li.find('a', class_='article-list-item__link')
            href = urljoin(BASE_URL, a['href'])
            title = a.get_text(strip=True)
            if '/articles/' in a['href'] and href not in seen:
                seen.add(href)
                new.append({'title': title, 'url': href})
        time.sleep(0.5)
    return new


def scrape_articles_content(links):
    out = []
    for i, art in enumerate(links, 1):
        print(f"[{i}/{len(links)}] {art['title']}")
        soup = get_soup(art['url'])
        h1 = soup.find('h1')
        title = h1.get_text(strip=True) if h1 else art['title']

        # seletor atualizado e fallback
        body = (
            soup.select_one('div.article-body') or
            soup.select_one('div.article__body') or
            soup.select_one('article.article-body') or
            soup.select_one('div.article__content')
        )
        if not body:
            body = soup.find('article')
        if body:
            paras = body.find_all('p')
            content = "\n\n".join(p.get_text(strip=True) for p in paras) if paras else body.get_text(strip=True)
        else:
            content = ""

        out.append({'title': title, 'url': art['url'], 'content': content})
        time.sleep(0.5)
    return out


def save_js(data):
    dest = VET_DIR / "articles_data.js"
    with open(dest, 'w', encoding='utf-8') as f:
        f.write('export const articlesData = ')
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write(';')
    print(f"\n✅ Gravados {len(data)} artigos em {dest}")


def main():
    print("1) Coletando seções e artigos diretos…")
    secs, arts = collect_sections_and_direct_articles()
    print(f"   → {len(secs)} seções, {len(arts)} artigos diretos")

    seen = {a['url'] for a in arts}
    more = collect_articles_from_sections(secs, seen)
    print(f"   → +{len(more)} artigos de seções")
    arts.extend(more)

    print("\n2) Raspando conteúdo dos artigos…")
    data = scrape_articles_content(arts)

    print("\n3) Salvando em JS…")
    save_js(data)


if __name__ == '__main__':
    main()
