import os
import fitz
import requests
import olefile
from flask import Flask, request, render_template, jsonify, send_from_directory
from openai import OpenAI
import markdown
from bs4 import BeautifulSoup

app = Flask(__name__)

def extract_text_from_pdf(pdf_path):
    try:
        document = fitz.open(pdf_path)
        text = ""
        for page_num in range(len(document)):
            page = document.load_page(page_num)
            text += page.get_text()
        return text
    except Exception as e:
        app.logger.error(f"Failed to extract text from PDF: {e}")
        return None

def extract_text_from_hwp(hwp_path):
    try:
        with olefile.OleFileIO(hwp_path) as f:
            encoded_text = f.openstream('PrvText').read()
            decoded_text = encoded_text.decode('utf-16')
        return decoded_text
    except Exception as e:
        app.logger.error(f"Failed to extract text from HWP: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download_and_redirect')
def download_and_redirect():
    url = request.args.get('url')
    title = request.args.get('title')
    region = request.args.get('region')
    region_folder = os.path.join("downloads", region)
    os.makedirs(region_folder, exist_ok=True)
    
    filename = title.replace(" ", "_") + ".pdf"
    filepath = os.path.join(region_folder, filename)

    # Check if the file already exists
    if not os.path.exists(filepath):
        response = requests.get(url)
        with open(filepath, 'wb') as f:
            f.write(response.content)

    output_pdf_text = extract_text_from_pdf(filepath)
    if not output_pdf_text:
        return f"Failed to extract text from PDF {filename}", 500

    client = OpenAI()

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a poetic assistant, skilled in summarizing pdf files."},
            {"role": "user", "content": f"신문지 같이 길게 정확하게 요약해줘.: {output_pdf_text}."}
        ]
    )

    summary = completion.choices[0].message.content

    summary_html = markdown.markdown(summary)
    summary_html = summary_html.replace('<p>- ', '<ul><li>').replace('\n- ', '</li><li>')
    summary_html = summary_html.replace('</li>\n</p>', '</li></ul></p>')

    return render_template('summary.html', title=title, summary=summary_html, file_type='pdf', file_path=f"/downloads/{os.path.join(region, filename)}")

@app.route('/downloads/<path:filename>')
def download_file(filename):
    return send_from_directory('downloads', filename)

@app.route('/fetch_incheon_titles')
def fetch_incheon_titles():
    url = 'https://www.incheon.go.kr/IC010205'
    response = requests.get(url)
    response.raise_for_status()
    
    parser = 'html.parser'
    soup = BeautifulSoup(response.text, parser)
    
    articles = []
    for item in soup.select('.board-blog-list ul li'):
        title = item.select_one('.subject').text.strip()
        link = item.select_one('a')['href']
        full_link = 'https://www.incheon.go.kr' + link
        articles.append({'title': title, 'link': full_link})
    
    return jsonify(articles)

@app.route('/fetch_gwangju_titles')
def fetch_gwangju_titles():
    url = 'https://www.gwangju.go.kr/boardList.do'
    params = {
        'pageId': 'www789',
        'boardId': 'BD_0000000027',
        'movePage': '1',
        'searchTy': 'TM'
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    
    parser = 'html.parser'
    soup = BeautifulSoup(response.text, parser)
    
    articles = []
    for item in soup.select('.board_list_body .body_row'):
        title = item.select_one('.subject a').text.strip()
        link = 'https://www.gwangju.go.kr' + item.select_one('.subject a')['href']
        seq = item.select_one('.subject a')['data-seq']
        articles.append({'title': title, 'link': link, 'seq': seq})
    
    return jsonify(articles)

@app.route('/fetch_ulsan_titles')
def fetch_ulsan_titles():
    url = 'https://www.ulsan.go.kr/u/rep/bbs/list.do'
    params = {
        'bbsId': 'BBS_0000000000000027',
        'mId': '001004003001000000'
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    
    parser = 'html.parser'
    soup = BeautifulSoup(response.text, parser)
    
    articles = []
    for item in soup.select('tbody tr'):
        title = item.select_one('td.ta_l a').text.strip()
        link = 'https://www.ulsan.go.kr' + item.select_one('td.ta_l a')['href']
        articles.append({'title': title, 'link': link})
    
    return jsonify(articles)

@app.route('/fetch_page', methods=['GET'])
def fetch_page():
    url = request.args.get('url')
    app.logger.info(f"Fetching page: {url}")
    response = requests.get(url)
    response.raise_for_status()
    return response.text

@app.route('/download_and_summarize_hwp')
def download_and_summarize_hwp():
    url = request.args.get('url')
    title = request.args.get('title')
    seq = request.args.get('seq')
    region = 'gwangju'
    region_folder = os.path.join("downloads", region)
    os.makedirs(region_folder, exist_ok=True)
    
    filename = f"{title.replace(' ', '_')}_{seq}.hwp"
    filepath = os.path.join(region_folder, filename)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    # Check if the file already exists
    if not os.path.exists(filepath):
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type')
            app.logger.info(f"Downloaded file content type: {content_type}")
            with open(filepath, 'wb') as f:
                f.write(response.content)
        else:
            return f"Failed to download HWP file from {url}", 400

    if os.path.getsize(filepath) == 0:
        return f"Downloaded HWP file is empty: {filename}", 400

    output_hwp_text = extract_text_from_hwp(filepath)
    if not output_hwp_text:
        return f"Failed to extract text from HWP {filename}", 500

    client = OpenAI()

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a poetic assistant, skilled in summarizing pdf files."},
            {"role": "user", "content": f"신문지 같이 길게 정확하게 요약해줘.: {output_hwp_text}."}
        ]
    )

    summary = completion.choices[0].message.content

    summary_html = markdown.markdown(summary)
    summary_html = summary_html.replace('<p>- ', '<ul><li>').replace('\n- ', '</li><li>')
    summary_html = summary_html.replace('</li>\n</p>', '</li></ul></p>')

    return render_template('summary.html', title=title, summary=summary_html, file_type='hwp', file_path=f"/downloads/{os.path.join(region, filename)}")

if __name__ == '__main__':
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    app.run(debug=True, host='0.0.0.0', port=6203)
