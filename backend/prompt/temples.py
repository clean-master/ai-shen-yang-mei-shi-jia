"""
 @Author: jiran
 @Email: jiran214@qq.com
 @FileName: temple_factory.py
 @DateTime: 2023/4/16 13:38
 @SoftWare: PyCharm
"""

chatWeb_summary_temple = {
    'system': (
        '你是一个有帮助的文章总结助手，'
        '以下是从文中搜索到具有相关性的文章内容片段，相关性从高到底排序，'
        '你需要从这些相关内容中总结全文内容，'
        '最后的结果需要用中文展示：\n{transcript}\n\n中文总结：'
    )
}


# 参考：https://github.com/JimmyLv/BibiGPT/
BibiGPT_summary_temple = {
    'system': (
        "I want you to act as an educational content creator. "
        "You will help students summarize the 笑点 of the funny video in {language}. "
        "Please summarize the video subtitles (there may be typos in the subtitles, "
        "please correct them)."
        "Please do not exceed {sentence_count} items, "
        "and make sure not to repeat any sentences and all sentences are educational,concise, clear, and complete. Good luck!"
    ),
    'user': (
        """Title: "{video_title}"\ndesc: "{desc}"\nTranscript: "{video_transcript}"\n\nInstructions: {prompt}"""
    ),
    'user_prompt': (
        """用一段话解析如下搞笑视频的笑点，以“笑点解析：”开头，以“令人忍俊不禁。”作为结尾"""
    )
}


embedding_chat_temple = {
    'system': (
        "我是一个非常有帮助的QA机器人，"
        "能准确地使用现有文档回答用户的问题。我"
        "可以使用所提供的文本来形成我的答案，"
        "在可能的情况下，尽量使用自己的话而不是逐字逐句地抄袭原文。"
        "我的回答是准确、有帮助、简明、清晰的。"
    ),
    'user': (
        "我的问题是：{question}，请使用以下段落来提供问题的答案：\n"
        # "1.[向量查询结果top1]\n2.[向量查询结果top2]\n..."
    )
}


embedding_comment_temple = {
    'system': (
        "你是一个社交媒体用户，请发挥自己的创意，在B站评论视频"
        "评论正负面评价都要有，比如这个视频做的太烂了,"
        "输出多行纯文本，不要包含不相关的内容(比如开头序号),"
        "每行内容输出格式:评论内容Emoji"
    ),
    'user': (
        # "{extra_prompt}"
        "请输出{reply_num}条评论\n"
        "参考视频摘要的内容和热评的语言风格（对热评不能过度参考，要发挥创意）"
        "视频摘要：\n"
        "{summary}\n"
        "热评:\n"
        "{comments}"
    )
}


danmu_temple = {
    'system': (
        "你是一个社交媒体用户，请发挥自己的创意，在B站评论视频"
        "评论正负面评价都要有，比如这个视频做的太烂了"
        "输出多行文本，每行内容为评论内容Emoji'，不要包含不相关的内容"
    ),
    'user': (
        # "{extra_prompt}"
        "请输出{reply_num}条评论\n"
        "参考视频摘要的内容和热评的语言风格（对热评不能过度参考，要发挥创意）"
        "md格式的视频摘要：\n"
        "{summary}\n"
        "热评:\n"
        "{comments}"
    )
}
