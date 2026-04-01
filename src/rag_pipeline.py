import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from .vector_store import get_vector_store

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

def build_rag_chain(retriever):
    """
    Builds the Retrieval-Augmented Generation (RAG) pipeline using LCEL.
    """
    # 1. Setup LLM
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

    # 2. Design the Prompt Template
    system_prompt = (
        "You are an expert AI financial analyst assistant. "
        "Use the following pieces of retrieved context to answer the user's question. "
        "If you don't know the answer based on the context, politely say that you don't know "
        "and do not make up an answer. "
        "Be concise, professional, and explain your reasoning based on the provided text.\n\n"
        "Context: {context}"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{question}"),
    ])

    # 3. Create LCEL Chain
    rag_chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    return rag_chain

def ask_question(query: str) -> dict:
    """
    Executes the RAG chain for a given query and returns the answer and source documents.
    """
    # Get retriever
    vector_store = get_vector_store()
    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 5}
    )
    
    # Run chain
    chain = build_rag_chain(retriever)
    answer = chain.invoke(query)
    
    # Get context documents manually for the UI
    context_docs = retriever.invoke(query)
    
    return {
        "answer": answer,
        "context": context_docs
    }

