"""
 @Author: jiran
 @Email: jiran214@qq.com
 @FileName: router.py
 @DateTime: 2023/4/7 16:30
 @SoftWare: PyCharm
"""
import json

import time

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends

# from starlette.responses import StreamingResponse
# from fastapi.responses import StreamingResponse
import log
from database.mongo_orm import NoteColl
from database.schema import BiliNoteForMongo
from prompt.schema import SummaryConfig
from requestor.bilibili import request_note_danmu
from schema import Document
from service import CrawlService, EmbeddingService, GPTService

from utils.timeutil import TimeRecord
from utils.video_id_transform import note_query_2_aid

embedding_router = APIRouter(
    prefix=''
)

logger = log.service_logger


# @embedding_router.get("/note_detail", summary='获取视频数据', description='', tags=['爬虫'])
async def find_note_schema_by_note_query(
        note_query: str
):
    # aid转换
    aid = note_query_2_aid(note_query)

    tr = TimeRecord(aid)
    t = tr.mark


    if True:
        # 采集视频资源
        crawl_service = CrawlService(aid=aid)
        documents, note_schema = await crawl_service.get_note_caption(t)
        logger.debug(f"aid:{aid}-获取字幕资源完成-cc字幕:{bool(note_schema.View.subtitle['list'])}-耗时{t()}")
        # 存储向量
        mongo_note_schema = BiliNoteForMongo(
                **note_schema.View.dict(),
                documents=documents,
                create_time=time.time()
            )
    return mongo_note_schema


@embedding_router.get("/summary", summary='获取视频向量，生成概要', description='', tags=['summary'])
async def summary(
        note_query: str, bt: BackgroundTasks,
        mongo_note_schema=Depends(find_note_schema_by_note_query)
):
    # 初始化
    embedding_total_tk = 0

    # aid转换
    aid = note_query_2_aid(note_query)

    tr = TimeRecord(aid)
    t = tr.mark

    # 缓存命中
    if mongo_note_schema and (summary_response := mongo_note_schema.summary_response):
        return summary_response

    documents = mongo_note_schema.documents
    top_n_documents = documents
    
    logger.debug(f'aid:{aid}-搜索概要语料完成-耗时{t()}')

    gpt_service = GPTService()
    note_view_schema = mongo_note_schema
    prompt_helper = gpt_service.get_summary_1(
        note_view_schema,
        documents=top_n_documents,
        config=SummaryConfig(
            emoji_show=True,
            sentence_count=7,
            words_count=15,
            language='Chinese'
        ))
    logger.debug(f'aid:{aid}-请求GPT生成概要完成-消耗tk:{prompt_helper.tk}-耗时{t()}\n{prompt_helper.assistant_content}')

    # summary = gpt_service.get_summary_2(documents=top_n_documents)

    res = {
        'related_content': [d.content for d in top_n_documents],
        'summary': prompt_helper.assistant_content,
        'embedding_total_tk': embedding_total_tk,
        'summary_total_tk': prompt_helper.total_tk
    }
    return res


@embedding_router.get("/chat", summary='和视频内容聊天', description='', tags=['chat'])
async def chat(
        note_query: str,
        question: str,
        mongo_note_schema=Depends(find_note_schema_by_note_query)
):
    # aid转换
    aid = note_query_2_aid(note_query)

    tr = TimeRecord(aid)
    t = tr.mark

    documents = mongo_note_schema.documents
    logger.debug(f'aid:{aid}-向量查询完成-耗时{t()}')

    embedding_service = EmbeddingService()
    # 搜索top 相关向量
    question_document, embedding_tk = embedding_service.get_embedding(Document(hash_id=hash(question), content=question))
    logger.debug(f'aid:{aid}-请求向量模型完成-消耗tk:{embedding_tk}-耗时{t()}')

    top_n_documents = embedding_service.search_top_n_with_vector_from_documents(question_document.embedding, documents, top=20)
    logger.debug(f'aid:{aid}-搜索chat语料完成-耗时{t()}')

    gpt_service = GPTService()
    prompt_helper = gpt_service.chat(question_document.content, documents=top_n_documents)
    logger.debug(f'aid:{aid}-请求GPT完成-消耗tk:{prompt_helper.tk}-耗时{t()}\n{prompt_helper.assistant_content}')

    return {
        '相关文本': [d.content for d in top_n_documents],
        '回答': prompt_helper.assistant_content,
        'chat使用token': prompt_helper.total_tk
    }


@embedding_router.get("/comment", summary='自动生成评论', description='', tags=['comment'])
async def comment(
        note_query: str,
        mongo_note_schema=Depends(find_note_schema_by_note_query)
):
    # aid转换
    aid = note_query_2_aid(note_query)

    tr = TimeRecord(aid)
    t = tr.mark

    if not mongo_note_schema.summary_response:
        raise HTTPException(status_code=500, detail="请先请求summary接口")

    # 获取评论
    crawl_service = CrawlService(aid)
    comments = await crawl_service.get_note_comment(limit=5)
    logger.debug(f'aid:{aid}-获取评论完成-耗时{t()}')

    note_summary = mongo_note_schema.summary_response['summary']
    logger.debug(f'aid:{aid}-获取summary完成-耗时{t()}')

    # 组成prompt，请求got
    gpt_service = GPTService()
    prompt_helper = gpt_service.get_comment(note_summary, comments)
    logger.debug(f'aid:{aid}-GPT请求完成-消耗tk:{prompt_helper.tk}-耗时{t()}')

    return {
        '生成的评论': prompt_helper.assistant_content.split('\n'),
        'chat使用token': prompt_helper.total_tk
    }

# @embedding_router.get("/comment", summary='自动生成弹幕', description='', tags=['comment'])
async def danmu(
        note_query: str,
        mongo_note_schema: BiliNoteForMongo=Depends(find_note_schema_by_note_query)
):
    # aid转换
    aid = mongo_note_schema.aid

    tr = TimeRecord(aid)
    t = tr.mark

    # 获取弹幕
    crawl_service = CrawlService(aid, mongo_note_schema.cid)
    content_list = await crawl_service.get_note_danmu()

    # 请求GPT

# todo 响应事件流
# condition = threading.Condition()
#
#
# class State:
#     def __init__(self):
#         self.messages = []
#         while 1:
#             self.update(['1', '2', '3', '4'])
#             print('1')
#             time.sleep(3)
#
#     def update(self, new_messages):
#         self.messages = new_messages
#         with condition:
#             print('3')
#             condition.notify()
#
#
# @embedding_router.get('/stream')
# def stream():
#     state = State()
#
#     def event_stream():
#         while True:
#             with condition:
#                 condition.wait()
#             print('2')
#             for message in state.messages:
#                 yield 'data: {}\n\n'.format(message)
#
#     return StreamingResponse(event_stream(), media_type="text/event-stream")
