import json
import spacy
from datetime import datetime
import os, requests
import pandas as pd
from fuzzywuzzy import fuzz
from utils import cache, mock_data_provider_api, timestamp_since, call_llm, MESSARI_API_KEY_TYPE

#ToDo: modularize insight engine which includes intent query, insight generate
DATA_PROVIDER = mock_data_provider_api()

# ---------------------- Prompt Building ----------------------
def _prompt(user_input: str) -> list:
    system_message = cache('prompt_system')
    user_message = cache('prompt_user').format(user_input=user_input)

    messages = []
    if system_message.strip() != "":
        messages.append({"role": "system","content": system_message}) 
    messages.append({"role": "user","content": user_message})
    return messages

# ---------------------- Parse LLM JSON Output ----------------------
def _parse_llm_output(output, key_word):
    # Extract JSON part manually
    return output.split("<"+key_word+">")[1].split("</"+key_word+">")[0] if key_word in output else output

# ---------------------- Extract Intent ----------------------
def _parse_intent(prompt_messages: str, mode="test") -> dict:
    if mode == "test":
        intent = cache(data="llm_output")
    else:
        intent = call_llm(prompt_messages)

        if intent.strip() in ["", None]:
            raise Exception("invald intent from calling llm")
     
    intent = json.loads(_parse_llm_output(intent, "output"))
    return intent

def intent_engine(user_input, mode="test"):
    prompt_messages = _prompt(user_input)
    intent = _parse_intent(prompt_messages, mode)
    return intent

# ---------------------- News API Request Generation ----------------------
def _news_intent_ner(intent, asset_list, category_list):
    '''
    named entity recognition (NER)
    '''
    # Load a small English model
    nlp = spacy.load("en_core_web_sm")

    # Run spaCy NLP pipeline
    doc = nlp(intent)

    # Extract potential entities
    tokens = [token.text for token in doc]

    # Match asset
    asset = next((asset for asset in asset_list if asset.lower() in [t.lower() for t in tokens]), "Others")

    # Match category by keyword
    category = None
    for cat in category_list:
        keyword = cat.split()[0]  # "scam" from "scam related"
        if any(keyword in token.lower() for token in tokens):
            category = cat
            break
    
    if not category:
        category = "Others"
        
    # Result
    result = {
        "asset": asset,
        "category": category
    }

    return result

def _news_intent2req(intent, data_provider, mode="test"):
    if mode == "test":
        return cache(data="req_from_news_intent")
    news_data_provider = DATA_PROVIDER["apiParams"]["News"]
    intent_ner = _news_intent_ner(intent['intent'], news_data_provider['asset'], news_data_provider['category'].keys())

    url, headers = news_data_provider["endpoint"], news_data_provider["headers"]
    params = {
        "assetIDs": [ data_provider["assetIds"][intent_ner["asset"]] ],
        "publishedAfter": timestamp_since()
    }

    headers["x-messari-api-key"] = os.getenv(MESSARI_API_KEY_TYPE)
    
    data_all = {}

    data_all['intent'] = {
        "assetId": data_provider["assetIds"][intent_ner['asset']],
        "keyWords": news_data_provider['category'][intent_ner['category']]['keyWords']
    }

    for page in range(1, news_data_provider["pages"]+1):
        params["page"] = page
        response = requests.get(url, headers=headers, params=params)
        # Check if the request was successful
        if response.status_code == 200:
            data = response.json()  # Get JSON data from the response
            
            if not data_all.get("data", None):
                data_all['data'] = data['data']
            else:
                data_all["data"].extend(data['data'])
            
            if page == news_data_provider["pages"]:
            # Save the data to a JSON file
                with open(f'data/intent_query.json', 'w') as json_file:
                    json.dump(data_all, json_file, indent=4)  # Save JSON with pretty print (indentation)
                return data_all
        else:
            return cache(data="req_from_news_intent")

# ---------------------- Convert API Data to DataFrame ----------------------
def _news_json2df(news_json):
    asset_id = news_json['intent']['assetId']
    # Filter and collect
    selected_items = []
    for item in news_json['data']:
        if any(asset.get("id") == asset_id for asset in item.get("assets", [])):
            publish_time_ms = item.get("publishTimeMillis")
            if publish_time_ms:
                publish_dt = datetime.utcfromtimestamp(publish_time_ms / 1000)
                # If date is in the future, replace with now
                if publish_dt > datetime.utcnow():
                    publish_time = datetime.utcnow().strftime('%Y-%m-%d')
                else:
                    publish_time = publish_dt.strftime('%Y-%m-%d')
            else:
                publish_time = None

            selected_items.append({
                "title": item.get("title"),
                "source": item.get("source", {}).get("sourceName"),
                "url": item.get("url"),
                "category": item.get("category"),
                "subcategory": item.get("subcategory"),
                "publish_time_utc": publish_time
            })

    # Turn into DataFrame
    news_df = pd.DataFrame(selected_items)
    return news_df

# ---------------------- Filter News via Fuzzy Match ----------------------
def _fuzzy_match(titles, keywords, threshold = 98):
    # Find related titles
    related_titles = []
    for title in titles:
        for keyword in keywords:
            if fuzz.partial_ratio(keyword.lower(), title.lower()) >= threshold:
                related_titles.append(title)
                break  # stop checking other keywords once matched
    return related_titles

# ---------------------- Full Intent → Data Request Pipeline ----------------------
def intent2req(intent, data_provider=DATA_PROVIDER, mode="test"):
    if intent["type"] == "News": # PoC has news intent only
        req_from_intent = _news_intent2req(intent, data_provider, mode)
        news_df = _news_json2df(req_from_intent)
        
        titles = news_df['title'].tolist()
        scam_keywords = req_from_intent['intent']['keyWords']

        scam_related_titles = _fuzzy_match(titles, scam_keywords)
        # Filter rows where title is in scam_related_titles
        filtered_df = news_df[news_df['title'].isin(scam_related_titles)].copy()

        # Ensure the publish_time_utc column is datetime type
        filtered_df['publish_time_utc'] = pd.to_datetime(filtered_df['publish_time_utc']).dt.strftime("%Y-%m-%d")

        # Select and rename relevant columns
        formatted_df = filtered_df.rename(columns={
            'title': 'Title',
            'url': 'Link',
            'source': 'Source',  # Adjust if your real source column is named differently
            'publish_time_utc': 'Date'
        })[['Title', 'Link', 'Source', 'Date']]

        # Sort by Date descending (newest first)
        formatted_df = formatted_df.sort_values(by='Date', ascending=False).reset_index(drop=True)
        return formatted_df
    else:
        pass # ToDo: add other intents 

# ---------------------- Insight Generation via LLM ----------------------
def deepthink(user_input, intent, insight_json):
    USER_MESSAGE_INSIGHT = cache("prompt_insight")

    # Generate insight
    insight_messages = [
        {"role": "system", "content": cache("prompt_system")},
        {"role": "user", "content": USER_MESSAGE_INSIGHT.format(category=intent['type'],insight_json=insight_json, intent_type=intent['type'])}
    ]
    
    insight_response = call_llm(insight_messages)

    USER_MESSAGE_DEEPTHINK = cache("prompt_deepthink")

    insight_messages.append({"role": "assistant", "content": insight_response})
    insight_messages.append({"role": "user", "content": USER_MESSAGE_DEEPTHINK.format(user_input=user_input, intent=intent['intent'])})
    deepthink_response = call_llm(insight_messages)
    deepthink_answer = deepthink_response.split("<DEEPTHINK>")[1].split("</DEEPTHINK>")[0] if "<DEEPTHINK>" in deepthink_response else deepthink_response
    return deepthink_answer

# ---------------------- Main Pipeline Entry ----------------------
def chatbot(user_input, mode="test"):
    if mode == "test":
        user_input = cache("user_input")

    intent = intent_engine(user_input)

    insight_df = intent2req(intent)

    insight_json = json.dumps(insight_df.to_dict(orient="records"), indent=4)

    deepthink_answer = deepthink(user_input, intent, insight_json)
    return deepthink_answer

if __name__ == "__main__":
    insight_result = chatbot(user_input="How to recognize scams in Solana?", mode="run")
    print(insight_result)