from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import CharacterTextSplitter, RecursiveCharacterTextSplitter
from langchain.document_loaders import TextLoader
from langchain.chains import RetrievalQA,  ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_chroma import Chroma
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain.output_parsers import ResponseSchema
from langchain.output_parsers import StructuredOutputParser
from langchain.output_parsers import CommaSeparatedListOutputParser


from dotenv import load_dotenv
import os
import openai

load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

llm_name = "gpt-4o"
llm = ChatOpenAI(model_name=llm_name, temperature=0)

########################variables###############################################

persist_directory = 'D:\Fai_personal\AI\Generative AI\MyProject\docs\db'
Chunk_size = 1000
Chunk_overlap = 150
K = 4
Chain_type = 'stuff'
db_flag  = 1   # 0: embed docuements and save to vector database, 1: use existing vector database
max_history_len = 10 #max number of latest chat history messages stored
session_id = "test123"
input_question = "Tell me more about the topics coverd in the machine learning class"
store={}

################################################################################

client = openai.OpenAI()
def get_completion(prompt, model=llm_name, temperature=0):
    messages = [{"role": "user", "content": prompt}]
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature, # this is the degree of randomness of the model's output
    )
    return response.choices[0].message.content


def get_session_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    if(len(store[session_id].messages) >= max_history_len):
        del store[session_id].messages[0:2]
    return store[session_id]

# Contextualize question into a standalone question based on chat history #
def create_standalone_question(input_question):
    contextualize_q_system_prompt2 = """Given a chat history and the latest user question \
    which might reference context in the chat history, formulate a standalone question \
    which can be understood without the chat history. Do NOT answer the question, \
    just reformulate it if needed and otherwise return it as is."""
    contextualize_q_prompt2 = ChatPromptTemplate.from_messages(
        [
            ("system", contextualize_q_system_prompt2),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )

    runnable = contextualize_q_prompt2 | llm
    
    standalone_question = runnable.invoke(
        {"input": input_question,
        "chat_history": get_session_history(session_id).messages}
        )
    return standalone_question

# Extract keywords from standalone question to be used for document retrieval filtering #
def extract_filter(standalone_question):
    extract_metadata_prompt = f"""extract all related keywords from the question below. Pick only the ones from the keyword list as follows. If you don't know what keyword to pick,
    answer as blank. 

    Keyword list: 
    - NT conference
    - Machine learning course
    - Intelligent operation center IOC
    - NT form
    - Smart pole

    Question: {standalone_question.content}

    Format the output in JSON as follows:
    question:<put the Question here>
    keyword:<put all related keywords here delimited by , as shown in example below or don't put anything here if no keyword in the Keyword list found>

    Example for keyword output:
    keyword: keyword1, keyword2, keyword3,...
    """

    response = get_completion(extract_metadata_prompt, model=llm_name, temperature=0.0)
    #print(response)

    # Parse LLM output and create a filter dictionary
    question_schema = ResponseSchema(name="question",
                                description="standalone question to be sent to another LLM call.")
    keyword_schema = ResponseSchema(name="keyword",
                                description="a list of keywords of the relavant document extracted from the standalone question.")

    response_schemas = [question_schema, 
                        keyword_schema]
    output_parser = StructuredOutputParser.from_response_schemas(response_schemas)
    output_dict = output_parser.parse(response)

    print(output_dict)


    # list of keywords extracted from the LLM output 
    list_parser = CommaSeparatedListOutputParser()
    lst = list_parser.parse(output_dict["keyword"]) 

    # Create a filter dictionary to filter by keywords
    filter_dict = {"keyword": {"$in": lst}}
    print(filter_dict)
    return filter_dict

# Create a retriever that filters the documents using filter dictionary (related keywords) #
def create_retrieval(K,filter_dict):   
    fembeddings = OpenAIEmbeddings()
    fdb = Chroma(persist_directory=persist_directory, embedding_function=fembeddings)
    fretriever = fdb.as_retriever(search_type="similarity", search_kwargs={"k": K, 'filter':filter_dict})
    print(persist_directory)
    return fretriever

class AskMe:
    def ask(self, input_question: str):
        '''#greeting = llm.invoke("Hello world!")
        #return greeting.content
        
        standalone_question = create_standalone_question(input_question)
        filter_dict = extract_filter(standalone_question)
        fretriever = create_retrieval(K,filter_dict)


        # Answer question #
        qa_system_prompt = """You are an assistant for question-answering tasks. \
        Use the following pieces of retrieved context to answer the question. \
        If you don't know the answer, just say that you don't know. \

        {context}"""

        qa_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", qa_system_prompt),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ]
        )
        question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)

        rag_chain = create_retrieval_chain(fretriever, question_answer_chain)


        conversational_rag_chain = RunnableWithMessageHistory(
            rag_chain,
            get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
            output_messages_key="answer",
        )
        print("I'm here"+standalone_question.content)
        response = conversational_rag_chain.invoke(
            {"input": standalone_question.content,
            "chat_history": {}},
            config={
                "configurable": {"session_id": session_id}
            }
        )'''
        
        greeting = llm.invoke(input_question)
        return greeting.content
        #return response


'''
chunk_size = 1024
chunk_overlap = 100
llm_model = "llama3" # llama3, mistral, gemma2

class AskMe:
    vector_store = None
    retriever = None
    chain = None

    

    def embed(self, pdf_file_path: str):
        docs = PyPDFLoader(file_path=pdf_file_path).load()
        chunks = self.text_splitter.split_documents(docs)
        chunks = filter_complex_metadata(chunks)

        vector_store = Chroma.from_documents(documents=chunks, embedding=FastEmbedEmbeddings())
        self.retriever = vector_store.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={
                "k":3,
                "score_threshold":0.5,
            },
        )

        self.chain = ({"context": self.retriever, "question": RunnablePassthrough()}
                      | self.prompt
                      | self.model
                      | StrOutputParser()
                      )

    def ask(self, query: str):
        if not self.chain:
            return "Please add a PDF document first."
        
        return self.chain.invoke(query)
    
    def clear(self):
        self.vector_store = None
        self.retriever = None
        self.chain = None
'''