import asyncio
import configparser
import video_id_transform
from bilibili_api import Credential, session
import sqlite3
import requests
from bilibili_api import comment
from bilibili_api.comment import CommentResourceType


conn = sqlite3.connect('data.db')
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS used_ids (
        id INTEGER PRIMARY KEY
    )
""")
url = "http://127.0.0.1:9090/summary?note_query="


def is_aid_used(aid):
    # 检查数据id是否已经存在于数据库中
    cursor.execute("SELECT * FROM used_ids WHERE id = ?", (aid,))
    result = cursor.fetchone()
    if result:
        return True

    cursor.execute("INSERT INTO used_ids (id) VALUES (?)", (aid,))
    conn.commit()

    return False


# 读取config.ini文件
config = configparser.ConfigParser()
config.read('config.ini')

# 获取sessdata、bili_jct和buvid3的值
sessdata = config.get('cookie', 'sessdata')
bili_jct = config.get('cookie', 'bili_jct')
buvid3 = config.get('cookie', 'buvid3')


async def main():
    credential = Credential(
        sessdata=sessdata, bili_jct=bili_jct, buvid3=buvid3)
    while True:
        try:
            sessions = await session.get_at(credential=credential)
            user_nickname = sessions['items'][0]['user']['nickname']
            source_content = sessions['items'][0]['item']['source_content']
            uri = sessions['items'][0]['item']['uri']
            source_id = sessions['items'][0]['item']['source_id']
            # 获取uri的BV
            bvid = "BV"+uri.split("BV")[1]
            aid = video_id_transform.note_query_2_aid(uri)
            print(user_nickname, source_content, uri, aid)

            if is_aid_used(aid) == True:
                await asyncio.sleep(10)
                continue
            # 添加查询aid
            query_url = url + bvid
            response = requests.get(query_url)
            response.raise_for_status()

            result = response.json()
            summary = result['summary'] + "\n" + "@"+user_nickname + " 问的。"
            # 发送评论
            await comment.send_comment(text=summary, type_=CommentResourceType.VIDEO, oid=aid, credential=credential)
            await asyncio.sleep(10)
        except Exception as e:
            if "500 Server Error" in str(e):
                print("500\n")
                summary = "解析出错，可能是不能识别到有效内容所导致的。"
                try:
                    await comment.send_comment(text=summary, type_=CommentResourceType.VIDEO, oid=aid, credential=credential, root=source_id)
                except Exception as comment_error:
                    print(f"Error while sending comment: {comment_error}")
            else:
                print(f"An error occurred: {e}")
            await asyncio.sleep(10)


# 运行异步函数
asyncio.run(main())

cursor.close()
conn.close()
# DELETE FROM used_ids WHERE id = 660222225;