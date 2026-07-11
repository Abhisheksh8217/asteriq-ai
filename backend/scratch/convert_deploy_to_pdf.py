import os
import markdown
from xhtml2pdf import pisa

def convert_md_to_pdf():
    md_path = r"C:\Users\HP\.gemini\antigravity\brain\a6b69167-f177-4854-a363-de9de265c01c\deployment_guide.md"
    pdf_path = r"C:\Users\HP\.gemini\antigravity\brain\a6b69167-f177-4854-a363-de9de265c01c\deployment_guide.pdf"
    
    if not os.path.exists(md_path):
        print(f"Error: Source markdown file not found at {md_path}")
        return
        
    print("Reading markdown file...")
    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()
        
    print("Converting Markdown to HTML...")
    # Enable extensions for tables and code highlights
    html_content = markdown.markdown(md_text, extensions=['extra', 'codehilite'])
    
    # Beautiful CSS Styling tailored for xhtml2pdf letter size
    styled_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: letter;
                margin: 0.8in;
            }}
            body {{
                font-family: Helvetica, Arial, sans-serif;
                color: #2d3748;
                line-height: 1.6;
                font-size: 10pt;
            }}
            h1 {{
                font-size: 22pt;
                color: #1a365d;
                margin-top: 0px;
                margin-bottom: 5px;
                border-bottom: 2px solid #3182ce;
                padding-bottom: 8px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            h2 {{
                font-size: 14pt;
                color: #2b6cb0;
                margin-top: 25px;
                margin-bottom: 10px;
                border-bottom: 1px solid #e2e8f0;
                padding-bottom: 4px;
            }}
            h3 {{
                font-size: 11pt;
                color: #2d3748;
                margin-top: 15px;
                margin-bottom: 5px;
                font-weight: bold;
            }}
            p {{
                margin-bottom: 12px;
                text-align: justify;
            }}
            ul, ol {{
                margin-bottom: 12px;
                margin-left: 20px;
            }}
            li {{
                margin-bottom: 6px;
            }}
            strong {{
                color: #1a202c;
            }}
            code {{
                font-family: Courier, monospace;
                background-color: #f7fafc;
                color: #e53e3e;
                padding: 1px 3px;
                font-size: 9.5pt;
            }}
            pre {{
                font-family: Courier, monospace;
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-left: 4px solid #4299e1;
                padding: 12px;
                margin-bottom: 15px;
                font-size: 8.5pt;
                line-height: 1.4;
            }}
            blockquote {{
                border-left: 4px solid #cbd5e0;
                padding-left: 12px;
                margin-left: 0px;
                margin-bottom: 15px;
                color: #4a5568;
                font-style: italic;
                background-color: #f7fafc;
                padding-top: 6px;
                padding-bottom: 6px;
            }}
            hr {{
                border: 0;
                border-top: 1px solid #e2e8f0;
                margin-top: 20px;
                margin-bottom: 20px;
            }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """
    
    print("Writing PDF file...")
    with open(pdf_path, "wb") as f_pdf:
        pisa_status = pisa.CreatePDF(styled_html, dest=f_pdf)
        
    if pisa_status.err:
        print("Error: PDF generation failed!")
    else:
        print(f"Success! PDF generated successfully at {pdf_path}")

if __name__ == "__main__":
    convert_md_to_pdf()
