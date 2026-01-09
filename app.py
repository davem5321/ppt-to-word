import streamlit as st
from pptx import Presentation
from docx import Document
from docx.shared import Inches, Pt
from io import BytesIO
import os
import tempfile

st.set_page_config(page_title="PowerPoint to Word Converter", page_icon="📄")

st.title("📄 PowerPoint to Word Converter")
st.write("Upload a PowerPoint file and convert it to a Word document")

# File uploader
uploaded_file = st.file_uploader("Drop your PowerPoint file here", type=['pptx', 'ppt'])

def convert_ppt_to_word(ppt_file):
    """Convert PowerPoint presentation to Word document"""
    # Load the presentation
    prs = Presentation(ppt_file)
    
    # Create a new Word document
    doc = Document()
    
    # Add a title
    doc.add_heading('PowerPoint Conversion', 0)
    
    # Iterate through slides
    for slide_idx, slide in enumerate(prs.slides, start=1):
        # Add slide number as heading
        doc.add_heading(f'Slide {slide_idx}', level=1)
        
        # Extract text from shapes
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                # Check if it's a title or content
                if shape.text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        text = paragraph.text.strip()
                        if text:
                            # Add paragraph with appropriate formatting
                            p = doc.add_paragraph(text)
                            # Apply basic formatting based on level
                            if paragraph.level == 0:
                                p.style = 'List Bullet'
                            else:
                                p.style = 'List Bullet 2'
            
            # Handle tables
            if shape.has_table:
                table = shape.table
                doc_table = doc.add_table(rows=len(table.rows), cols=len(table.columns))
                doc_table.style = 'Light Grid Accent 1'
                
                for i, row in enumerate(table.rows):
                    for j, cell in enumerate(row.cells):
                        doc_table.rows[i].cells[j].text = cell.text
        
        # Add a page break after each slide (except the last one)
        if slide_idx < len(prs.slides):
            doc.add_page_break()
    
    # Save to BytesIO object
    doc_buffer = BytesIO()
    doc.save(doc_buffer)
    doc_buffer.seek(0)
    
    return doc_buffer

if uploaded_file is not None:
    try:
        with st.spinner('Converting PowerPoint to Word...'):
            # Convert uploaded file bytes to BytesIO object
            ppt_stream = BytesIO(uploaded_file.getvalue())
            
            # Convert the presentation
            word_file = convert_ppt_to_word(ppt_stream)
            
            # Success message
            st.success('✅ Conversion completed successfully!')
            
            # Generate filename
            original_filename = uploaded_file.name
            base_filename = os.path.splitext(original_filename)[0]
            word_filename = f"{base_filename}_converted.docx"
            
            # Download button
            st.download_button(
                label="📥 Download Word Document",
                data=word_file,
                file_name=word_filename,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            
            st.info(f"📝 Your converted document is ready: {word_filename}")
            
    except Exception as e:
        st.error(f"❌ Error during conversion: {str(e)}")
        st.write("Please make sure you uploaded a valid PowerPoint file (.pptx)")
else:
    st.info("👆 Please upload a PowerPoint file to begin")

# Footer
st.markdown("---")
st.markdown("*Built with Streamlit, python-pptx, and python-docx*")
