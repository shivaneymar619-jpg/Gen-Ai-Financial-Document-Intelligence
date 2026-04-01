import streamlit as st
import tempfile
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.document_loader import load_documents
from src.chunking import split_documents
from src.vector_store import add_documents_to_store
from src.rag_pipeline import ask_question

# Streamlit Page Config
st.set_page_config(
    page_title="GenAI Financial Document Intelligence",
    page_icon="🏦",
    layout="wide"
)

def main():
    st.title("🏦 GenAI-Powered Financial Document Intelligence System")
    st.markdown("""
    Upload your financial documents (PDFs, images) and interact with them using Generative AI. 
    The system uses Retrieval-Augmented Generation (RAG) to provide accurate answers directly from your documents.
    """)

    # --- Sidebar for File Upload ---
    with st.sidebar:
        st.header("Upload Documents")
        uploaded_files = st.file_uploader(
            "Upload Bank Statements, Invoices, etc.", 
            type=['pdf', 'png', 'jpg', 'jpeg'], 
            accept_multiple_files=True
        )

        if st.button("Process Documents"):
            if uploaded_files:
                with st.spinner("Processing documents..."):
                    all_chunks = []
                    
                    for uploaded_file in uploaded_files:
                        # Save uploaded file to a temporary location
                        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            tmp_path = tmp_file.name
                        
                        try:
                            # 1. Load Document (PDF Parsing / OCR)
                            docs = load_documents(tmp_path)
                            
                            # 2. Chunk Text
                            chunks = split_documents(docs)
                            all_chunks.extend(chunks)
                            
                        except Exception as e:
                            st.error(f"Error processing {uploaded_file.name}: {e}")
                        finally:
                            os.remove(tmp_path)
                            
                    if all_chunks:
                        # 3. Store in Vector DB
                        add_documents_to_store(all_chunks)
                        st.success(f"Successfully processed {len(uploaded_files)} files into {len(all_chunks)} text chunks!")
                    else:
                        st.warning("No text could be extracted from the uploaded files.")
            else:
                st.warning("Please upload at least one file.")

    # --- Main Chat Area ---
    st.header("Ask Questions")
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # React to user input
    if prompt := st.chat_input("E.g., What is the total amount due on the invoice?"):
        # Display user message in chat message container
        st.chat_message("user").markdown(prompt)
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Get AI response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = ask_question(prompt)
                    answer = response.get("answer", "No answer generated.")
                    sources = response.get("context", [])
                    
                    st.markdown(answer)
                    
                    # Display Sources
                    if sources:
                        with st.expander("Sources (Click to view)"):
                            for i, doc in enumerate(sources):
                                source_name = doc.metadata.get("source", "Unknown")
                                page_num = doc.metadata.get("page", "N/A")
                                st.markdown(f"**Source {i+1}:** {source_name} (Page: {page_num})")
                                st.markdown(f"*{doc.page_content[:200]}...*")
                    
                    # Add assistant response to chat history
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                    
                except Exception as e:
                    st.error(f"An error occurred: {e}")
                    st.info("Make sure you have processed some documents first and your API key is valid.")

if __name__ == "__main__":
    main()
