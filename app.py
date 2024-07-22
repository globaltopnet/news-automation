import os
import fitz
import requests
from flask import Flask, request, render_template, jsonify, send_from_directory
from openai import OpenAI
import markdown

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download')
def download_article():
    url = request.args.get('url')
    title = request.args.get('title')
    filename = title.replace(" ", "_") + ".pdf"
    filepath = os.path.join("downloads", filename)

    # Check if the file already exists
    if not os.path.exists(filepath):
        response = requests.get(url)
        with open(filepath, 'wb') as f:
            f.write(response.content)

    return jsonify({'success': True, 'filename': filename})

@app.route('/summarize')
def summarize_article():
    filename = request.args.get('filename')
    title = request.args.get('title')
    filepath = os.path.join("downloads", filename)

    if not os.path.exists(filepath):
        return f"File {filename} not found", 404

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

    # Replace double newlines with paragraph tags for better spacing and handle lists
    summary_html = markdown.markdown(summary)
    summary_html = summary_html.replace('<p>- ', '<ul><li>').replace('\n- ', '</li><li>')
    summary_html = summary_html.replace('</li>\n</p>', '</li></ul></p>')

    return render_template('summary.html', summary=summary_html, title=title, pdf_path=f"/downloads/{filename}")

@app.route('/downloads/<filename>')
def download_file(filename):
    return send_from_directory('downloads', filename)

if __name__ == '__main__':
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    app.run(debug=True)
