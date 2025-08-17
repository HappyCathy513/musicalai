import pandas as pd
import numpy as np
import re
import jieba
import os
from flask import Flask, request, jsonify
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime
from collections import defaultdict
import hashlib
import sqlite3

# 尝试读取Excel文件，支持多种路径
excel_file_paths = [
    "音乐剧元数据3_转换后_20250810_035559.xlsx",  # 相对路径
    "音乐剧元数据3_转换后.xlsx",  # 备用文件名
    "音乐剧元数据3.xlsx"  # 另一个备用文件名
]

df = None
excel_read_success = False

# 首先尝试读取Excel文件
for excel_file_path in excel_file_paths:
    try:
        print(f"🔍 尝试读取Excel文件: {excel_file_path}")
        if os.path.exists(excel_file_path):
            print(f"📁 文件存在，开始读取...")
            df = pd.read_excel(excel_file_path, sheet_name=0, usecols=['剧名','导演','剧种','题材','地域','情绪'])
            print(f"✅ 成功读取Excel文件: {excel_file_path}，共{len(df)}条记录")
            excel_read_success = True
            break
        else:
            print(f"❌ 文件不存在: {excel_file_path}")
    except Exception as e:
        print(f"❌ 读取Excel文件失败: {excel_file_path} - {e}")
        continue

# 如果所有Excel文件都读取失败，使用内置数据
if not excel_read_success:
    print("⚠️ 所有Excel文件读取失败，使用内置数据")
    print("📊 创建内置音乐剧数据...")
    
    # 扩展内置数据，提供更丰富的推荐
    df = pd.DataFrame({
        '剧名': [
            '悲惨世界', '歌剧魅影', '猫', '西贡小姐', '芝加哥', '妈妈咪呀', '狮子王', 
            '美女与野兽', '阿拉丁', '小美人鱼', '罗密欧与朱丽叶', '哈姆雷特', '麦克白',
            '奥赛罗', '李尔王', '仲夏夜之梦', '威尼斯商人', '第十二夜', '皆大欢喜', '暴风雨'
        ],
        '导演': [
            '克劳德-米歇尔·勋伯格', '安德鲁·劳埃德·韦伯', 'Trevor Nunn', '克劳德-米歇尔·勋伯格', 
            'Bob Fosse', 'Phyllida Lloyd', 'Julie Taymor', 'Alan Menken', 'Alan Menken', 
            'Alan Menken', '莎士比亚', '莎士比亚', '莎士比亚', '莎士比亚', '莎士比亚',
            '莎士比亚', '莎士比亚', '莎士比亚', '莎士比亚', '莎士比亚'
        ],
        '剧种': [
            '音乐剧', '音乐剧', '音乐剧', '音乐剧', '音乐剧', '音乐剧', '音乐剧', 
            '音乐剧', '音乐剧', '音乐剧', '话剧', '话剧', '话剧', '话剧', '话剧',
            '话剧', '话剧', '话剧', '话剧', '话剧'
        ],
        '题材': [
            '革命·救赎', '爱情·疯癫', '群像·生命赞歌', '战争·爱情', '犯罪·歌舞', 
            '亲情·音乐', '成长·冒险', '爱情·魔法', '冒险·魔法', '爱情·海洋',
            '爱情·悲剧', '复仇·悲剧', '野心·悲剧', '嫉妒·悲剧', '权力·悲剧',
            '爱情·喜剧', '贪婪·喜剧', '爱情·喜剧', '爱情·喜剧', '魔法·喜剧'
        ],
        '地域': [
            '法式', '法式', '百老汇', '法式', '美式', '英式', '美式', '美式', '美式', '美式',
            '英式', '英式', '英式', '英式', '英式', '英式', '英式', '英式', '英式', '英式'
        ],
        '情绪': [
            '悲壮', '悲剧', '悲喜交织', '悲壮', '喜剧', '温馨', '励志', '温馨', '冒险', '温馨',
            '悲剧', '悲剧', '悲剧', '悲剧', '悲剧', '喜剧', '喜剧', '喜剧', '喜剧', '喜剧'
        ]
    })
    print(f"✅ 使用内置数据，共{len(df)}条记录")
    print("💡 内置数据包含经典音乐剧和话剧，确保推荐系统正常工作")

def database():
    """创建数据库表"""
    try:
        # 使用绝对路径，确保在 Render 环境中能正确创建
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 创建 user_behavior.db
        behavior_db_path = os.path.join(current_dir, 'user_behavior.db')
        print(f"创建数据库: {behavior_db_path}")
        
        conn = sqlite3.connect(behavior_db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS user_searches
                     (user_id TEXT, play_id INTEGER, timestamp DATETIME)''')
        conn.commit()
        conn.close()
        print("✅ user_behavior.db 表创建成功")

        # 创建 user_mapping.db
        mapping_db_path = os.path.join(current_dir, 'user_mapping.db')
        print(f"创建数据库: {mapping_db_path}")
        
        conn = sqlite3.connect(mapping_db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS user_mapping
                     (code TEXT PRIMARY KEY, user_id TEXT)''')
        conn.commit()
        conn.close()
        print("✅ user_mapping.db 表创建成功")
        
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        # 如果失败，尝试使用相对路径
        try:
            print("尝试使用相对路径创建数据库...")
            
            conn = sqlite3.connect('user_behavior.db')
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS user_searches
                         (user_id TEXT, play_id INTEGER, timestamp DATETIME)''')
            conn.commit()
            conn.close()
            
            conn = sqlite3.connect('user_mapping.db')
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS user_mapping
                         (code TEXT PRIMARY KEY, user_id TEXT)''')
            conn.commit()
            conn.close()
            
            print("✅ 使用相对路径创建数据库成功")
            
        except Exception as e2:
            print(f"❌ 相对路径也失败: {e2}")
            raise e2

def get_user_id(code):
    """获取或创建用户ID"""
    try:
        # 尝试使用绝对路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, 'user_mapping.db')
        conn = sqlite3.connect(db_path)
    except:
        # 如果失败，使用相对路径
        conn = sqlite3.connect('user_mapping.db')
    
    c = conn.cursor()
    c.execute("SELECT user_id FROM user_mapping WHERE code=?", (code,))
    row = c.fetchone()
    if row is not None:
        conn.close()
        return row[0]
    else:
        user_id = hashlib.md5(f"{code}{datetime.now()}".encode()).hexdigest()
        c.execute("INSERT INTO user_mapping VALUES (?, ?)", (code, user_id))
        conn.commit()
        conn.close()
        return user_id

def search_number(user_id, play_name):
    """记录用户搜索行为"""
    try:
        print(f"尝试记录搜索: 用户ID={user_id}, 音乐剧名称='{play_name}'")
        print(f"可用的音乐剧名称示例: {df['剧名'].head(10).tolist()}")
        
        # 检查是否存在完全匹配
        exact_match = df[df['剧名'] == play_name]
        if exact_match.empty:
            print(f"未找到完全匹配的音乐剧: '{play_name}'")
            # 尝试模糊匹配
            partial_matches = df[df['剧名'].str.contains(play_name, na=False)]
            if not partial_matches.empty:
                print(f"找到部分匹配: {partial_matches['剧名'].tolist()}")
            return False
        
        play_id = exact_match.index[0]
        # 确保play_id是整数
        play_id = int(play_id)
        print(f"找到匹配的音乐剧，ID: {play_id}")
        
        try:
            # 尝试使用绝对路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(current_dir, 'user_behavior.db')
            conn = sqlite3.connect(db_path)
        except:
            # 如果失败，使用相对路径
            conn = sqlite3.connect('user_behavior.db')
        
        c = conn.cursor()
        c.execute("INSERT INTO user_searches VALUES (?, ?, ?)",
                  (user_id, play_id, datetime.now()))
        conn.commit()
        conn.close()
        print(f"记录用户 {user_id} 搜索 {play_name} (ID: {play_id}) 成功")
        return True
    except Exception as e:
        print(f"记录搜索行为失败: {e}")
        return False

def split(text):
    """分割文本，处理多个标签"""
    text=str(text)
    if pd.isna(text) or text == '':
        return []
    a=re.split(r'[/&、·]',text)
    result=[]
    for i in a:
        if i!='' and i.strip()!='':
            result.append(i.strip())
    return result

def preprocess(df):
    """预处理数据"""
    df['导演']=df['导演'].apply(split)
    df['题材']=df['题材'].apply(split)
    return df

# 预处理数据
df=preprocess(df)

# 添加自定义词汇到jieba
try:
    custom_words=['话剧','音乐剧','舞剧','肢体剧','歌剧','芭蕾舞剧','现代舞剧','民族舞剧']
    for a in custom_words:
        jieba.add_word(a)
    print("✅ jieba自定义词汇添加成功")
except Exception as e:
    print(f"⚠️ jieba自定义词汇添加失败: {e}")
    # 继续执行，不影响主要功能

def cut(text):
    """分词处理"""
    text=str(text)
    if pd.isna(text) or text == '':
        return []
    words=jieba.lcut(text)
    result=[]
    for i in words:
        if i.strip()!='':  # 修复了原来的bug
            result.append(i.strip())
    return result

# 处理剧种、地域、情绪
df['剧种']=df['剧种'].apply(cut)
df['地域']=df['地域'].apply(cut)
df['情绪']=df['情绪'].apply(cut)

# 创建特征矩阵
mlb=MultiLabelBinarizer()
director_matrix=mlb.fit_transform(df['导演'])
theme_matrix=mlb.fit_transform(df['题材'])
genre_matrix=mlb.fit_transform(df['剧种'])
mood_matrix=mlb.fit_transform(df['情绪'])
region_matrix=mlb.fit_transform(df['地域'])

# 合并所有特征
feature_matrix=np.hstack([director_matrix,theme_matrix,genre_matrix,region_matrix,mood_matrix])
content=cosine_similarity(feature_matrix)
np.fill_diagonal(content,0)

def comprehensive_similarity(user_id):
    """计算协同过滤相似度"""
    try:
        try:
            # 尝试使用绝对路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(current_dir, 'user_behavior.db')
            conn = sqlite3.connect(db_path)
        except:
            # 如果失败，使用相对路径
            conn = sqlite3.connect('user_behavior.db')
        
        c = conn.cursor()
        # 获取用户搜索记录，按时间排序，最近的记录权重更高
        c.execute("SELECT play_id, timestamp FROM user_searches WHERE user_id=? ORDER BY timestamp DESC", (user_id,))
        rows = c.fetchall()
        user_plays = set()
        recent_plays = set()  # 最近3次的搜索
        play_weights = {}  # 每个剧的权重
        
        # 统计每个音乐剧的搜索次数和最近搜索时间
        play_counts = defaultdict(int)
        play_last_seen = {}
        
        for i, row in enumerate(rows):
            play_id = row[0]
            timestamp = row[1]
            
            # 处理字节格式的play_id
            if isinstance(play_id, bytes):
                try:
                    # 尝试将字节转换为整数
                    play_id = int.from_bytes(play_id, byteorder='little')
                except:
                    print(f"无法转换字节ID: {play_id}")
                    continue
            
            # 确保play_id在有效范围内
            if isinstance(play_id, (int, float)) and 0 <= play_id < len(df):
                play_id = int(play_id)
                user_plays.add(play_id)
                play_counts[play_id] += 1
                play_last_seen[play_id] = i  # 记录最近搜索的位置
        
        # 计算权重：基于搜索次数和最近搜索时间
        for play_id in user_plays:
            count = play_counts[play_id]
            last_seen = play_last_seen[play_id]
            
            # 基础权重：搜索次数
            base_weight = min(count, 3.0)  # 最多3.0
            
            # 时间权重：最近搜索给予更高权重
            if last_seen < 3:
                time_weight = 3.0
            elif last_seen < 5:
                time_weight = 2.0
            else:
                time_weight = 1.0
            
            # 综合权重
            play_weights[play_id] = base_weight * time_weight
            
            # 记录最近搜索的音乐剧
            if last_seen < 3:
                recent_plays.add(play_id)
        
        conn.close()
        
        print(f"用户搜索记录: {len(user_plays)}个, 最近搜索: {len(recent_plays)}个")
        if recent_plays:
            recent_names = [df.iloc[pid]['剧名'] for pid in recent_plays if pid < len(df)]
            print(f"最近搜索的剧: {recent_names}")

        if not user_plays:
            # 如果用户没有搜索记录，返回基于内容相似度的推荐
            return content.mean(axis=0)

        # 计算用户与其他用户的相似度
        n=len(df)
        result=np.zeros(n)
        
        # 重新连接数据库获取所有用户的搜索记录
        try:
            # 尝试使用绝对路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(current_dir, 'user_behavior.db')
            conn = sqlite3.connect(db_path)
        except:
            # 如果失败，使用相对路径
            conn = sqlite3.connect('user_behavior.db')
        
        c = conn.cursor()
        c.execute("SELECT user_id, play_id FROM user_searches")
        all_user_searches = c.fetchall()
        conn.close()
        
        # 构建用户-物品矩阵
        user_item_matrix = defaultdict(set)
        for user_id_search, play_id in all_user_searches:
            if isinstance(play_id, (int, float)) and 0 <= play_id < len(df):
                user_item_matrix[user_id_search].add(int(play_id))
        
        # 计算协同过滤分数
        for i in range(n):
            if i in user_plays:
                result[i] = 0  # 用户已经看过的剧不推荐
            else:
                # 基于内容相似度计算推荐分数，使用权重
                if i < len(content):
                    similar_plays = content[i]
                    # 给用户看过的剧的相似剧加分，使用权重
                    for user_play in user_plays:
                        if user_play < len(similar_plays):
                            try:
                                weight = play_weights.get(user_play, 1.0)  # 获取权重，默认1.0
                                result[i] += float(similar_plays[user_play]) * weight
                            except (ValueError, TypeError):
                                # 如果转换失败，跳过这个值
                                continue
                
                # 添加内容相似度作为基础分数 - 减少权重
                if i < len(content.mean(axis=0)):
                    try:
                        result[i] += float(content.mean(axis=0)[i]) * 0.1  # 减少权重从0.3到0.1
                    except (ValueError, TypeError):
                        # 如果转换失败，使用默认值
                        result[i] += 0.0
        
        return result
    except Exception as e:
        print(f"协同过滤计算错误: {e}")
        # 如果出错，返回基于内容的推荐
        return content.mean(axis=0)

def recommend_top5(user_id: str, top_k: int = 5):
    """推荐前5个音乐剧"""
    try:
        uid = user_id  # 直接使用传入的user_id
        try:
            # 尝试使用绝对路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(current_dir, 'user_behavior.db')
            conn = sqlite3.connect(db_path)
        except:
            # 如果失败，使用相对路径
            conn = sqlite3.connect('user_behavior.db')
        
        rows = conn.execute("SELECT play_id FROM user_searches WHERE user_id=?", (uid,)).fetchall()
        seen = set()
        for row in rows:
            play_id = row[0]
            # 处理字节格式的play_id
            if isinstance(play_id, bytes):
                try:
                    play_id = int.from_bytes(play_id, byteorder='little')
                except:
                    print(f"无法转换字节ID: {play_id}")
                    continue
            if isinstance(play_id, (int, float)) and 0 <= play_id < len(df):
                seen.add(int(play_id))
        conn.close()

        # 计算综合推荐分数
        s1=comprehensive_similarity(uid)
        s2=content.mean(axis=0)
        
        # 确保两个数组都是numpy数组且长度一致
        if isinstance(s1, np.ndarray) and isinstance(s2, np.ndarray):
            if len(s1) != len(s2):
                # 如果长度不一致，使用较短的数组长度
                min_len = min(len(s1), len(s2))
                s1 = s1[:min_len]
                s2 = s2[:min_len]
        else:
            # 如果不是numpy数组，转换为numpy数组
            s1 = np.array(s1) if s1 is not None else np.zeros(len(df))
            s2 = np.array(s2) if s2 is not None else np.zeros(len(df))
        
        # 混合推荐策略 - 根据用户行为数量动态调整权重
        user_behavior_count = len(seen)
        if user_behavior_count == 0:
            # 新用户，主要基于内容推荐
            blended = 0.2 * s1 + 0.8 * s2
        elif user_behavior_count <= 2:
            # 少量行为，平衡推荐
            blended = 0.5 * s1 + 0.5 * s2
        elif user_behavior_count <= 5:
            # 中等行为，偏向个性化
            blended = 0.8 * s1 + 0.2 * s2
        else:
            # 大量行为，强烈个性化
            blended = 0.9 * s1 + 0.1 * s2
        
        print(f"用户行为数量: {user_behavior_count}, 个性化权重: {blended[0] if len(blended) > 0 else 'N/A'}")

        # 创建推荐分数Series
        scores=pd.Series(blended, index=df['剧名'].iloc[:len(blended)])
        
        # 过滤掉用户已经看过的剧
        if seen:
            try:
                # 确保seen中的索引在有效范围内
                valid_seen = [idx for idx in seen if isinstance(idx, (int, float)) and 0 <= idx < len(df)]
                if valid_seen:
                    seen_names = df.iloc[valid_seen]['剧名'].tolist()
                    scores = scores[~scores.index.isin(seen_names)]
            except Exception as e:
                print(f"过滤已看过的剧时出错: {e}")
                # 如果出错，继续使用未过滤的分数
        
        # 返回推荐结果，包含剧名和相似度分数
        top_scores = scores.sort_values(ascending=False).head(top_k)
        recommendations = []
        for play_name, score in top_scores.items():
            recommendations.append({
                '剧名': play_name,
                'similarity': round(float(score), 4),
                '导演': df[df['剧名'] == play_name]['导演'].iloc[0] if not df[df['剧名'] == play_name].empty else '未知',
                '剧种': df[df['剧名'] == play_name]['剧种'].iloc[0] if not df[df['剧名'] == play_name].empty else '未知'
            })
        
        # 记录推荐结果到日志
        print(f"用户 {uid} 的推荐结果: {[r['剧名'] for r in recommendations]}")
        
        return recommendations
    except Exception as e:
        print(f"推荐计算错误: {e}")
        # 如果出错，返回基于内容的简单推荐
        try:
            content_scores = content.mean(axis=0)
            scores = pd.Series(content_scores, index=df['剧名'])
            top_scores = scores.sort_values(ascending=False).head(top_k)
            recommendations = []
            for play_name, score in top_scores.items():
                recommendations.append({
                    '剧名': play_name,
                    'similarity': round(float(score), 4),
                    '导演': df[df['剧名'] == play_name]['导演'].iloc[0] if not df[df['剧名'] == play_name].empty else '未知',
                    '剧种': df[df['剧名'] == play_name]['剧种'].iloc[0] if not df[df['剧名'] == play_name].empty else '未知'
                })
            return recommendations
        except:
            # 最后的备选方案
            recommendations = []
            for i, play_name in enumerate(df['剧名'].head(top_k)):
                recommendations.append({
                    '剧名': play_name,
                    'similarity': 0.5,  # 默认相似度
                    '导演': df.iloc[i]['导演'] if i < len(df) else '未知',
                    '剧种': df.iloc[i]['剧种'] if i < len(df) else '未知'
                })
            return recommendations

# Flask应用
app = Flask(__name__)

@app.route('/search', methods=['POST'])
def api_search():
    """记录用户搜索行为"""
    try:
        data = request.get_json()
        # 修改：同时接受 code 或直接的 userId
        code = data.get('code')
        user_id = data.get('userId') # <--- 新增
        play_name = data.get('play_name')
        
        # 如果没有直接提供 userId，则通过 code 获取
        if not user_id and code:
            user_id = get_user_id(code)
        
        if not user_id or not play_name:
            return jsonify({'error': '缺少 user_id 或 play_name 参数'}), 400
        
        print(f"API - 获取到用户ID: {user_id}")
        
        search_success = search_number(user_id, play_name)
        
        if search_success:
            return jsonify({
                'success': True,
                'message': f'记录用户 {user_id} 搜索 {play_name} 成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'未找到音乐剧: {play_name}'
            }), 404
            
    except Exception as e:
        print(f"搜索API错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/recommend', methods=['GET'])
def api_recommend():
    """推荐API接口"""
    try:
        # 获取参数
        code = request.args.get('code')
        user_id = request.args.get('userId')

        # 如果没有直接提供 userId，则通过 code 获取
        if not user_id and code:
            try:
                user_id = get_user_id(code)
                print(f"通过code获取到user_id: {user_id}")
            except Exception as e:
                print(f"获取user_id失败: {e}")
                return jsonify({'error': f'获取用户ID失败: {str(e)}'}), 400

        if not user_id:
            return jsonify({'error': '缺少 user_id 或 code 参数'}), 400
        
        print(f"开始为用户 {user_id} 计算推荐...")
        
        # 调用推荐函数
        top5 = recommend_top5(user_id)
        print(f"推荐计算完成，返回 {len(top5)} 个推荐")
        
        return jsonify({
            'success': True,
            'data': top5,
            'total': len(top5)
        })
    except Exception as e:
        print(f"推荐API错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    try:
        # 检查数据库连接
        db_status = "unknown"
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            behavior_db_path = os.path.join(current_dir, 'user_behavior.db')
            conn = sqlite3.connect(behavior_db_path)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM user_searches")
            search_count = c.fetchone()[0]
            conn.close()
            db_status = "connected"
        except Exception as e:
            db_status = f"error: {str(e)}"
            search_count = 0
        
        return jsonify({
            'status': 'healthy',
            'data_loaded': len(df) if df is not None else 0,
            'database_status': db_status,
            'search_records': search_count,
            'timestamp': datetime.now().isoformat(),
            'environment': {
                'python_version': f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
                'working_directory': os.getcwd(),
                'files_in_dir': len([f for f in os.listdir('.') if f.endswith('.xlsx')])
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

if __name__ == '__main__':
    print("🚀 初始化音乐剧推荐系统...")
    print("=" * 50)
    
    # 检查数据加载状态
    if df is not None and len(df) > 0:
        print(f"✅ 数据加载成功，共{len(df)}条记录")
        print(f"📊 数据示例:")
        for i, row in df.head(3).iterrows():
            print(f"   {i+1}. {row['剧名']} - {row['导演']} - {row['剧种']}")
    else:
        print("❌ 数据加载失败！")
        exit(1)
    
    # 确保数据库表存在
    try:
        database()
        print("✅ 数据库初始化完成")
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        print("⚠️ 尝试继续启动服务...")
    
    # 检查jieba分词器
    try:
        test_text = "音乐剧爱好者"
        words = jieba.lcut(test_text)
        print(f"✅ jieba分词器正常，测试: '{test_text}' -> {words}")
    except Exception as e:
        print(f"⚠️ jieba分词器异常: {e}")
    
    print("=" * 50)
    print("🎯 启动Flask服务...")
    
    # 端口改为 Render 需要的 $PORT
    port = int(os.environ.get("PORT", 3000))
    print(f"🌐 服务将在端口 {port} 上启动")
    print(f"🔗 健康检查: http://localhost:{port}/health")
    print(f"🎭 推荐接口: http://localhost:{port}/recommend")
    print(f"🔍 搜索接口: http://localhost:{port}/search")
    
    app.run(host='0.0.0.0', port=port)