import json, os, re, time
import multiprocessing as mp
from functools import partial
import random
import uuid
from datasets import load_dataset
from evaluate import load as load_metric
import streamlit as st
from agno.agent import Agent
from agno.agent import AgentKnowledge
from agno.knowledge.pdf import PDFKnowledgeBase, PDFReader
from agno.vectordb.qdrant import Qdrant
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.reasoning import ReasoningTools
from agno.models.openai import OpenAIChat
from agno.embedder.openai import OpenAIEmbedder
from agno.team.team import Team
import tempfile
import os
from agno.document.chunking.document import DocumentChunking
from agno.knowledge.text import TextKnowledgeBase

OPENAI_API_KEY=""
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

qdrant_api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.G6ZK06QnWMBzKXfDr0quLl_bdL7yXK1z0azfrnIpgXU"
qdrant_url = "https://fd0f2387-645d-4d44-bb59-02909affd364.us-west-1-0.aws.cloud.qdrant.io"

def compute_token_f1(prediction_text, reference_text):
    """计算两个文本片段之间的token-level F1分数"""
    if not prediction_text.strip() or not reference_text.strip():
        return 0.0
    
    # 简单的token化（按空格分割）
    pred_tokens = set(prediction_text.lower().split())
    ref_tokens = set(reference_text.lower().split())
    
    if not pred_tokens or not ref_tokens:
        return 0.0
    
    # 计算重叠
    overlap = len(pred_tokens & ref_tokens)
    
    if overlap == 0:
        return 0.0
    
    precision = overlap / len(pred_tokens)
    recall = overlap / len(ref_tokens)
    
    f1 = 2 * precision * recall / (precision + recall)
    return f1

def classify_sample(prediction_texts, reference_texts):
    """
    根据CUAD评测规则对样本进行TP/FP/FN分类
    
    Args:
        prediction_texts: 预测的文本片段列表
        reference_texts: 参考答案文本片段列表
    
    Returns:
        tuple: (classification, max_f1)
        classification: 'TP', 'FP', 'FN', 'TN'
        max_f1: 最大F1分数
    """
    has_prediction = len(prediction_texts) > 0 and any(text.strip() for text in prediction_texts)
    has_reference = len(reference_texts) > 0 and any(text.strip() for text in reference_texts)
    
    if not has_prediction and not has_reference:
        return 'TN', 0.0  # True Negative - 正确地没有预测
    
    if not has_prediction and has_reference:
        return 'FN', 0.0  # False Negative - 漏检
    
    if has_prediction and not has_reference:
        return 'FP', 0.0  # False Positive - 误报
    
    # 都有预测和参考答案，计算最大F1
    max_f1 = 0.0
    for pred_text in prediction_texts:
        if not pred_text.strip():
            continue
        for ref_text in reference_texts:
            if not ref_text.strip():
                continue
            f1 = compute_token_f1(pred_text, ref_text)
            max_f1 = max(max_f1, f1)
    
    # 根据F1阈值判断TP或FP
    if max_f1 > 0.0:  # CUAD通常以F1>0为阈值
        return 'TP', max_f1
    else:
        return 'FP', max_f1

def process_single_sample(sample_data, openai_key, qdrant_url, qdrant_api_key):
    """处理单个样本的函数"""
    try:
        i, row = sample_data
        
        # 1. 启动时随机延迟，避免同时开始
        startup_delay = random.uniform(0.5, 1.5)
        time.sleep(startup_delay)
        
        qid = row["id"]
        contract = row["context"]
        question = row["question"]
        answers_text  = row["answers"]["text"]
        answer_starts = row["answers"]["answer_start"]
        
        print(f"Processing sample {i}: {qid.split('__')[-1]} (delay: {startup_delay:.1f}s)")
        
        # 构建 reference
        if not isinstance(answers_text, list):
            answers_text = [answers_text]

        if not isinstance(answer_starts, list):
            answer_starts = [answer_starts]

        reference = {
            "id": qid,
            "answers": {
                "text": answers_text,             # list[str]
                "answer_start": answer_starts   # list[int]
            },
        }
        
        # 处理预测
        prediction_texts = []
        
        try:
            # 2. 添加预处理延迟
            pre_build_delay = random.uniform(0.2, 0.8)
            time.sleep(pre_build_delay)
            
            # 3. 为每个样本创建唯一的集合名，避免冲突
            unique_suffix = f"{i}_{str(uuid.uuid4())[:8]}_{int(time.time()*1000) % 10000}"
            
            # 4. 修改 build_team 以接受自定义集合名
            team_lead = build_team_with_unique_collection(
                contract,
                openai_key,
                qdrant_url,
                qdrant_api_key,
                collection_suffix=unique_suffix
            )
            
            # 5. API 调用前延迟
            pre_api_delay = random.uniform(0.3, 1.0)
            time.sleep(pre_api_delay)
            
            reply = team_lead.run(question).content
            
            # 6. API 调用后延迟
            post_api_delay = random.uniform(0.5, 1.2)
            time.sleep(post_api_delay)
            
            if not reply or not reply.strip():
                prediction_texts = []
            else:
                # 清理响应内容
                reply_cleaned = reply.strip()
                
                # 移除 markdown 代码块标记
                if '```json' in reply_cleaned:
                    start = reply_cleaned.find('```json') + 7
                    end = reply_cleaned.rfind('```')
                    if end > start:
                        reply_cleaned = reply_cleaned[start:end].strip()
                elif '```' in reply_cleaned:
                    start = reply_cleaned.find('```') + 3
                    end = reply_cleaned.rfind('```')
                    if end > start:
                        reply_cleaned = reply_cleaned[start:end].strip()
                
                # 解析 JSON
                try:
                    data = json.loads(reply_cleaned)
                    
                    # 处理返回数组的情况
                    if isinstance(data, list) and len(data) > 0:
                        data = data[0]
                        
                except json.JSONDecodeError:
                    # 尝试提取 JSON 部分
                    if '{' in reply_cleaned and '}' in reply_cleaned:
                        start_idx = reply_cleaned.find('{')
                        end_idx = reply_cleaned.find('}') + 1
                        json_part = reply_cleaned[start_idx:end_idx]
                        data = json.loads(json_part)
                    else:
                        data = None
                
                if data and isinstance(data, dict):
                    span_text = data.get("text", "")
                    start_char = data.get("start_char", -1)
                    
                    if start_char != -1 and span_text.strip():
                        prediction_texts = [span_text]
                        print(f"✓ Sample {i}: Found answer")
                    else:
                        prediction_texts = []
                        print(f"✗ Sample {i}: No answer")
                else:
                    prediction_texts = []
                    print(f"✗ Sample {i}: Invalid data format")
                    
        except Exception as e:
            print(f"✗ Sample {i}: Error - {str(e)[:150]}...")
            # 错误发生时延迟更长时间
            error_delay = random.uniform(1.0, 2.0)
            time.sleep(error_delay)
            prediction_texts = []
        
        # 构建 prediction
        prediction = {
            'id': qid,
            'prediction_text': prediction_texts,
        }
        
        # 对样本进行TP/FP/FN分类
        classification, max_f1 = classify_sample(prediction_texts, answers_text)
        
        print(f"Sample {i} classification: {classification} (F1: {max_f1:.3f})")
        
        # 7. 完成时延迟
        completion_delay = random.uniform(0.2, 0.5)
        time.sleep(completion_delay)
        
        return i, prediction, reference, len(prediction_texts) > 0, classification, max_f1
        
    except Exception as e:
        print(f"✗ Sample {sample_data[0]}: Critical error - {e}")
        critical_delay = random.uniform(2.0, 3.0)
        time.sleep(critical_delay)
        return sample_data[0], None, None, False, 'ERROR', 0.0

def build_team_with_unique_collection(contract_text: str, openai_key: str, qdrant_url: str = None, qdrant_api_key: str = None, collection_suffix: str = None):
    """修改版的 build_team，使用唯一集合名"""
    
    # 使用唯一的集合名
    unique_collection = f"legal_contracts_{collection_suffix}" if collection_suffix else f"legal_contracts_{uuid.uuid4().hex[:8]}"
    
    if qdrant_url and qdrant_api_key:
        vector_db = Qdrant(
            collection=unique_collection,  # 使用唯一集合名
            url=qdrant_url,
            api_key=qdrant_api_key,
            embedder=OpenAIEmbedder(id="text-embedding-3-small", api_key=openai_key)
        )
    else:
        from agno.vectordb.memory import MemoryVectorDb
        vector_db = MemoryVectorDb(
            embedder=OpenAIEmbedder(id="text-embedding-3-small", api_key=openai_key)
        )
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as temp_file:
        temp_file.write(contract_text)
        temp_file_path = temp_file.name
    
    try:
        kb = TextKnowledgeBase(
            path=temp_file_path,
            chunking_strategy=DocumentChunking(chunk_size=500, overlap=100), # Changed chunk_size from 1000 to 500 and adjusted overlap
            vector_db=vector_db,
        )
        
        # 加载知识库
        kb.load()
        
    finally:
        # 清理临时文件
        try:
            os.unlink(temp_file_path)
        except Exception:
            pass

    # 创建代理
    researcher = Agent(
        name="Legal Researcher",
        role="Legal research specialist",
        model=OpenAIChat(id="gpt-4o-mini", temperature=0.0),
        tools=[DuckDuckGoTools()],
        knowledge=kb,
        search_knowledge=True,
        instructions=[
            "Find and cite relevant legal cases, precedents or frameworks",
            "Provide detailed research summaries with sources",
            "Reference specific sections from the knowledge base",
            "Always search the knowledge base for relevant information"
        ],
        show_tool_calls=True,
        markdown=False
    )

    # Contract Analyst Agent
    analyst = Agent(
        name="Contract Analyst",
        role="Contract analysis specialist",
        model=OpenAIChat(id="gpt-4o-mini", temperature=0.0),
        knowledge=kb,
        search_knowledge=True,
        instructions=[
            "Review the uploaded contract thoroughly",
            "Always rely on the legal researcher if need any external information, such as risk assessment framework or legal precedent",
            "Identify key terms and potential issues",
            "Reference specific clauses from the document"
        ],
        markdown=True
    )

    # Legal Strategist Agent
    strategist = Agent(
        name="Legal Strategist", 
        role="Legal strategy specialist",
        model=OpenAIChat(id="gpt-4o-mini", temperature=0.0),
        knowledge=kb,
        search_knowledge=True,
        instructions=[
            "Develop comprehensive legal strategies based on knowledge base",
            "Provide actionable recommendations",
            "Consider both risks and opportunities using legal precedents"
        ],
        markdown=False
    )

    # Team-lead 代理
    team_lead = Team(
        name="Lead",
        mode="coordinate",
        model=OpenAIChat(id="gpt-4o-mini", temperature=0.0),  # Zero temperature for consistency
        tools=(
            ReasoningTools(
                think=True,
                analyze=True,
                add_instructions=True,
                add_few_shot=True,
            ),
        ),
        members=[researcher, analyst, strategist],
        knowledge=kb,
        search_knowledge=True,
        instructions=[
            "You are the Lead of a legal team, coordinating a Legal Researcher, a Contract Analyst, and a Legal Strategist. Your primary task is to identify and extract a specific clause from a contract based on a given question.",
            "CRITICAL: You must return ONLY ONE valid JSON object in this exact format:",
            '{"text": "exact clause text from contract", "start_char": 123, "end_char": 456}',
            "",
            "HOW TO WORK WITH YOUR TEAM AND THE CONTRACT:",
            "1. Understand the user's question to determine the specific type of clause to find.",
            "2. Instruct your team members (Researcher, Analyst, Strategist) to search the provided contract for text relevant to the question. Each team member will respond with either the direct text of a potentially relevant clause or 'NONE'.",
            "3. Review the clauses provided by your team. If multiple clauses are suggested, consult with your Strategist to help determine which single clause is the MOST specific and directly answers the question.",
            "4. Once the single most specific clause is identified from the team's input or your own analysis of the contract:",
            "   a. Extract the EXACT, verbatim text of this clause from the original contract document.",
            "   b. Accurately determine the 'start_char' (the index of the first character of the clause) and 'end_char' (the index of the character immediately after the last character of the clause) within the original contract text. For example, if the contract is 'The cat sat.' and the clause is 'cat', start_char would be 4 and end_char would be 7.",
            "",
            "IMPORTANT OUTPUT RULES:",
            "1. Your final response MUST be ONLY ONE JSON object. Do not return a list or multiple JSON objects.",
            "2. If your team finds multiple relevant clauses, you must select only the single MOST specific clause for the final output. Do not include multiple clauses in the 'text' field.",
            "3. The 'text' field in the JSON must contain the EXACT verbatim text of the selected clause as it appears in the contract. Do not paraphrase or add any extra information.",
            "4. The 'start_char' and 'end_char' values must be precise character offsets corresponding to the extracted 'text' in the original contract.",
            "5. If, after thorough analysis with your team, no relevant clause can be found in the contract that directly answers the question, you MUST return: {'text': '', 'start_char': -1, 'end_char': -1}",
            "6. Your response must contain ONLY the JSON object. No explanations, apologies, introductory phrases, markdown formatting (like ```json), or any other text outside the JSON structure is permitted.",
            "7. Ensure the JSON is perfectly valid and can be parsed by Python's `json.loads()`."
        ],
        markdown=False,
        show_members_responses=True,
        show_tool_calls=False
    )
    return team_lead

def main():
    # 加载数据集
    ds = load_dataset("theatticusproject/cuad-qa", split="test", trust_remote_code=True)
    metric = load_metric("cuad")
    
    # 并行处理配置 - 减少进程数和样本数以提高稳定性
    sample_size = 100 # 减少样本数
    num_processes = 2  # 减少进程数
    
    print(f"Total samples: {len(ds)}, Testing with {sample_size} samples")
    print(f"Using {num_processes} parallel processes with unique collections")
    
    # 准备数据
    sample_data = [(i, ds[i]) for i in range(min(sample_size, len(ds)))]
    
    # 并行处理
    start_time = time.time()
    
    with mp.Pool(num_processes) as pool:
        # 使用 partial 来传递固定参数
        process_func = partial(
            process_single_sample,
            openai_key=OPENAI_API_KEY,
            qdrant_url=qdrant_url,
            qdrant_api_key=qdrant_api_key
        )
        
        # 并行处理所有样本
        results = pool.map(process_func, sample_data)
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    # 整理结果
    predictions = []
    references = []
    successful_samples = 0
    sample_classifications = []
    
    # 按原始顺序排序结果
    results = sorted([r for r in results if r[1] is not None], key=lambda x: x[0])
    
    for i, prediction, reference, success, classification, max_f1 in results:
        if prediction and reference:
            predictions.append(prediction)
            references.append(reference)
            if success:
                successful_samples += 1
            
            # 记录每个样本的分类信息
            sample_classifications.append({
                'sample_id': i,
                'question_id': prediction['id'],
                'classification': classification,
                'max_f1': max_f1,
                'has_prediction': len(prediction['prediction_text']) > 0,
                'has_reference': len(reference['answers']['text']) > 0,
                'prediction_text': prediction['prediction_text'],
                'reference_text': reference['answers']['text']
            })
    
    # 统计分类结果
    classification_counts = {'TP': 0, 'FP': 0, 'FN': 0, 'TN': 0, 'ERROR': 0}
    for sample in sample_classifications:
        classification_counts[sample['classification']] += 1
    
    # 输出统计信息
    print(f"\n" + "="*80)
    print(f"PARALLEL PROCESSING WITH UNIQUE COLLECTIONS COMPLETED")
    print(f"="*80)
    print(f"Total processing time: {processing_time:.1f} seconds")
    print(f"Average time per sample: {processing_time/len(results):.1f} seconds")
    print(f"Successful predictions: {successful_samples}/{len(results)}")
    print(f"Success rate: {successful_samples/len(results)*100:.1f}%")
    
    print(f"\nSample Classification Results:")
    print(f"TP (True Positive): {classification_counts['TP']}")
    print(f"FP (False Positive): {classification_counts['FP']}")
    print(f"FN (False Negative): {classification_counts['FN']}")
    print(f"TN (True Negative): {classification_counts['TN']}")
    print(f"ERROR: {classification_counts['ERROR']}")
    
    # 计算指标
    tp = classification_counts['TP']
    fp = classification_counts['FP']
    fn = classification_counts['FN']
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    print(f"\nManual Metrics:")
    print(f"Precision: {precision:.3f}")
    print(f"Recall: {recall:.3f}")
    print(f"F1: {f1:.3f}")
    
    # 输出每个样本的详细分类信息
    print(f"\nDetailed Sample Classifications:")
    for sample in sample_classifications:
        print(f"Sample {sample['sample_id']}: {sample['classification']} "
              f"(F1: {sample['max_f1']:.3f}, ID: {sample['question_id'].split('__')[-1]})")
    
    # 保存结果
    with open("predictions_cuad_parallel_fixed.json", "w") as f:
        json.dump({
            "predictions": predictions, 
            "references": references,
            "sample_classifications": sample_classifications,
            "classification_counts": classification_counts,
            "manual_metrics": {
                "precision": precision,
                "recall": recall,
                "f1": f1
            },
            "metadata": {
                "total_samples": len(results),
                "successful_samples": successful_samples,
                "processing_time": processing_time,
                "num_processes": num_processes,
                "unique_collections": True
            }
        }, f, indent=2)
    
    # CUAD 评估
    if predictions and references:
        try:
            print(f"\nRunning CUAD evaluation...")
            eval_results = metric.compute(predictions=predictions, references=references)
            print(f"\nOfficial CUAD Results on {len(predictions)} samples:")
            for key, value in eval_results.items():
                print(f"{key}: {value}")
                
        except Exception as e:
            print(f"Evaluation error: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("No valid predictions to evaluate")

if __name__ == "__main__":
    mp.freeze_support()
    main()