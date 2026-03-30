import os, psycopg2
from contextlib import contextmanager
from langchain_openai import AzureChatOpenAI
from dotenv import load_dotenv
load_dotenv()

@contextmanager
def get_conn():
    conn = psycopg2.connect(
        host=os.getenv("PGHOST"),
        user=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD"),
        database=os.getenv("PGDATABASE")
    )
    try:
        yield conn
    finally:
        conn.close()

def retrieve_chunks(question, top_k=5):
    sql = """
    WITH q AS (SELECT azure_openai.create_embeddings(%s,%s)::vector AS qvec)
    SELECT id, title, policy_text
    FROM company_policies, q
    ORDER BY embedding <=> q.qvec
    LIMIT %s;
    """
    params= (os.getenv("OPENAI_EMBED_DEPLOYMENT"), question, top_k)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return [{"id": r[0], "title": r[1], "policy_text": r[2]} for r in rows]

SYSTEM_PROMPT = """
You are a helpful assistant answering about company policies. Answer using ONLY the provided context.
If the answer is not in the context, say you don’t have enough information.
Cite policy titles in square brackets, e.g., [Vacation policy].
"""
def format_context(chunks):
    return "\n\n".join([f"{c['policy_text']} [{c['title']}]" for c in chunks])

def generate_answer(question, chunks):
    llm = AzureChatOpenAI(
        azure_deployment=os.getenv("OPENAI_CHAT_DEPLOYMENT"),
        api_key=os.getenv("AZURE_OPENAI_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version=os.getenv("AZURE_OPENAI_VERSION"),
        temperature=0
    )
    context = format_context(chunks)
    messages = [
        ("system", SYSTEM_PROMPT),
        ("human", f"Question: {question}\nContext:\n{context}")
    ]
    return llm.invoke(messages).content

def answer(question):
    chunks = retrieve_chunks(question)
    if not chunks:
        return "No relevant policies found."
    return generate_answer(question, chunks)

print(answer("i want to resign, what should I prepare before?"))