from flask import Flask, request, jsonify, g
import sqlite3
import random
import os
from flask_cors import CORS

# 初始化Flask应用
app = Flask(__name__)
CORS(app)  # 允许跨域访问（前端和后端域名不同时需要）

# 数据库配置
DATABASE = 'question_bank.db'

# 获取数据库连接
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row  # 让查询结果可以按字段名访问
    return db

# 关闭数据库连接
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# 初始化数据库表（首次运行自动创建）
def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        # 创建试题表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                answer TEXT NOT NULL,
                score INTEGER NOT NULL
            )
        ''')
        db.commit()

# 初始化数据库
init_db()

# ------------------- API接口 -------------------
# 1. 获取所有试题
@app.route('/api/questions', methods=['GET'])
def get_questions():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM questions ORDER BY id DESC')
    questions = [dict(row) for row in cursor.fetchall()]
    return jsonify(questions)

# 2. 添加/编辑试题
@app.route('/api/question', methods=['POST'])
def save_question():
    data = request.json
    db = get_db()
    cursor = db.cursor()
    
    if data.get('id'):
        # 编辑试题
        cursor.execute('''
            UPDATE questions 
            SET type=?, content=?, answer=?, score=? 
            WHERE id=?
        ''', (data['type'], data['content'], data['answer'], data['score'], data['id']))
    else:
        # 新增试题
        cursor.execute('''
            INSERT INTO questions (type, content, answer, score)
            VALUES (?, ?, ?, ?)
        ''', (data['type'], data['content'], data['answer'], data['score']))
    
    db.commit()
    return jsonify({'success': True, 'message': '试题保存成功'})

# 3. 删除试题
@app.route('/api/question/<int:id>', methods=['DELETE'])
def delete_question(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute('DELETE FROM questions WHERE id=?', (id,))
    db.commit()
    return jsonify({'success': True, 'message': '试题删除成功'})

# 4. 批量导入试题
@app.route('/api/import', methods=['POST'])
def import_questions():
    data = request.json
    type = data['type']
    score = data['score']
    questions = data['questions']
    answers = data['answers']
    
    if len(questions) != len(answers):
        return jsonify({'success': False, 'message': '题目和答案数量不一致'}), 400
    
    db = get_db()
    cursor = db.cursor()
    success_count = 0
    
    for q, a in zip(questions, answers):
        if q.strip() and a.strip():
            cursor.execute('''
                INSERT INTO questions (type, content, answer, score)
                VALUES (?, ?, ?, ?)
            ''', (type, q.strip(), a.strip(), score))
            success_count += 1
    
    db.commit()
    return jsonify({'success': True, 'message': f'成功导入{success_count}道试题'})

# 5. 随机生成试卷
@app.route('/api/generate-paper', methods=['POST'])
def generate_paper():
    data = request.json
    # 获取配置
    choice_count = data.get('choice_count', 0)
    choice_score = data.get('choice_score', 0)
    fill_count = data.get('fill_count', 0)
    fill_score = data.get('fill_score', 0)
    short_count = data.get('short_count', 0)
    short_score = data.get('short_score', 0)
    calc_count = data.get('calc_count', 0)
    calc_score = data.get('calc_score', 0)
    
    # 校验总分
    total = (choice_count * choice_score) + (fill_count * fill_score) + (short_count * short_score) + (calc_count * calc_score)
    if total != 100:
        return jsonify({'success': False, 'message': '总分不是100分'}), 400
    
    # 查询各题型试题
    db = get_db()
    cursor = db.cursor()
    
    # 选择题
    cursor.execute('SELECT * FROM questions WHERE type=?', ('选择题',))
    choice_questions = [dict(row) for row in cursor.fetchall()]
    if choice_count > len(choice_questions):
        return jsonify({'success': False, 'message': f'选择题数量不足（仅{len(choice_questions)}道）'}), 400
    
    # 填空题
    cursor.execute('SELECT * FROM questions WHERE type=?', ('填空题',))
    fill_questions = [dict(row) for row in cursor.fetchall()]
    if fill_count > len(fill_questions):
        return jsonify({'success': False, 'message': f'填空题数量不足（仅{len(fill_questions)}道）'}), 400
    
    # 简答题
    cursor.execute('SELECT * FROM questions WHERE type=?', ('简答题',))
    short_questions = [dict(row) for row in cursor.fetchall()]
    if short_count > len(short_questions):
        return jsonify({'success': False, 'message': f'简答题数量不足（仅{len(short_questions)}道）'}), 400
    
    # 计算题
    cursor.execute('SELECT * FROM questions WHERE type=?', ('计算题',))
    calc_questions = [dict(row) for row in cursor.fetchall()]
    if calc_count > len(calc_questions):
        return jsonify({'success': False, 'message': f'计算题数量不足（仅{len(calc_questions)}道）'}), 400
    
    # 随机抽取试题
    def shuffle_and_pick(arr, count):
        shuffled = random.sample(arr, len(arr))
        return shuffled[:count]
    
    selected_choice = shuffle_and_pick(choice_questions, choice_count)
    selected_fill = shuffle_and_pick(fill_questions, fill_count)
    selected_short = shuffle_and_pick(short_questions, short_count)
    selected_calc = shuffle_and_pick(calc_questions, calc_count)
    
    return jsonify({
        'success': True,
        'data': {
            'choice': selected_choice,
            'fill': selected_fill,
            'short': selected_short,
            'calc': selected_calc,
            'config': {
                'choice_count': choice_count,
                'choice_score': choice_score,
                'fill_count': fill_count,
                'fill_score': fill_score,
                'short_count': short_count,
                'short_score': short_score,
                'calc_count': calc_count,
                'calc_score': calc_score
            }
        }
    })

# 启动应用
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))