import json
import logging
import subprocess
import time
from datetime import datetime, timedelta
 
import pandas as pd
import requests
from tabulate import tabulate
import openpyxl
from openpyxl.chart import PieChart, Reference
from openpyxl.chart.label import DataLabelList
 
request_count = 0
last_request_time = None
 
def increment_request_count():
    global request_count, last_request_time
    request_count += 1
    current_time = time.time()
    if last_request_time is not None:
        interval = current_time - last_request_time
        logging.info(f"Number of requests made: {request_count} | Interval since last request: {interval:.2f} seconds")
    else:
        logging.info(f"Number of requests made: {request_count} | This is the first request.")
    last_request_time = current_time
 
def setup_logging():
    """Set up basic logging configuration."""
    logging.basicConfig(level=logging.INFO)
def handle_errors(exception, message):
    logging.error(f"{message}: {exception}")
    exit(1)
def find_common_prefix(strings):
    """Find the longest common prefix among a list of strings."""
    if not strings:
        return ""
    shortest_str = min(strings, key=len)
    for i, char in enumerate(shortest_str):
        for other in strings:
            if other[i] != char:
                return shortest_str[:i]
    return shortest_str
def get_subscription_ids(subscription_prefix):
    try:
        result = subprocess.run(
            ["az", "account", "list"],
            capture_output=True,
            text=True,
            check=True
        )
        increment_request_count()  # Incrementa o contador de requisições
        subscriptions = json.loads(result.stdout)
        subscription_ids = [
            (subscription['name'], subscription['id'])
            for subscription in subscriptions
            if subscription['name'].startswith(subscription_prefix)
        ]
        if not subscription_ids:
            logging.error(f"No subscriptions found with prefix '{subscription_prefix}'.")
            exit(1)
        return subscription_ids
    except subprocess.CalledProcessError as e:
        handle_errors(e, "Command error")
    except json.JSONDecodeError as e:
        handle_errors(e, "JSON decode error")
    except Exception as e:
        handle_errors(e, "Unexpected error")
def get_access_token():
    try:
        result = subprocess.run(
            ["az", "account", "get-access-token", "--resource=https://management.azure.com/"],
            capture_output=True,
            text=True,
            check=True
        )
        increment_request_count()  # Incrementa o contador de requisições
        token_info = json.loads(result.stdout)
        return token_info['accessToken']
    except subprocess.CalledProcessError as e:
        handle_errors(e, "Command error")
    except json.JSONDecodeError as e:
        handle_errors(e, "JSON decode error")
    except Exception as e:
        handle_errors(e, "Unexpected error")
def get_analysis_timeframe(start_date_str=None, period=31):
    if start_date_str:
        end_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    else:
        end_date = datetime.utcnow() - timedelta(days=1)
    start_date = end_date - timedelta(days=period)
    timeframe = {
        "from": start_date.strftime('%Y-%m-%d'),
        "to": end_date.strftime('%Y-%m-%d')
    }
    return start_date, end_date, timeframe
def build_cost_management_request(subscription_id, grouping_type, grouping_name, access_token):
    cost_management_url = f'https://management.azure.com/subscriptions/{subscription_id}/providers/Microsoft.CostManagement/query?api-version=2021-10-01'
    start_date, end_date, timeframe = get_analysis_timeframe()
    payload = {
        "type": "ActualCost",
        "timeframe": "Custom",
        "timePeriod": timeframe,
        "dataset": {
            "granularity": "Daily",
            "aggregation": {
                "totalCost": {
                    "name": "Cost",
                    "function": "Sum"
                }
            },
            "grouping": []
        }
    }
    if grouping_type.lower() != 'subscription':
        payload["dataset"]["grouping"].append({
            "type": grouping_type,
            "name": grouping_name
        })
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    return cost_management_url, payload, headers
 
def check_alert(cost_yesterday, average_cost):
    return "Yes" if cost_yesterday > (average_cost + 0.10) else "No"

def process_costs(costs_by_group, grouping_key, start_date, end_date, analysis_date_str):
    results = []
    analysis_date = datetime.strptime(analysis_date_str, '%Y%m%d')
    is_analysis_date_weekend = analysis_date.weekday() >= 5

    for group_value, costs in costs_by_group.items():
        weekday_costs = []
        weekend_costs = []

        for single_date in (start_date + timedelta(n) for n in range((end_date - start_date).days + 1)):
            date_int = int(single_date.strftime('%Y%m%d'))
            day_cost = next((cost for date, cost in costs if date == date_int), 0)
            if single_date.weekday() >= 5:
                weekend_costs.append(day_cost)
            else:
                weekday_costs.append(day_cost)

        relevant_costs = weekend_costs if is_analysis_date_weekend else weekday_costs
        total_days = len(relevant_costs)
        total_cost = sum(relevant_costs)

        average_cost = total_cost / total_days if total_days > 0 else 0
        cost_on_analysis_date = next((cost for date, cost in costs if date == int(analysis_date_str)), 0)

        if total_days > 1:
            variance = sum((x - average_cost) ** 2 for x in relevant_costs) / (total_days - 1)
            standard_deviation = variance ** 0.5
        else:
            standard_deviation = 0

        alert = check_alert(cost_on_analysis_date, average_cost)
        percent_variation = ((cost_on_analysis_date - average_cost) / average_cost) * 100 if average_cost != 0 else 0
        cost_difference = cost_on_analysis_date - average_cost

        results.append({
            grouping_key: group_value,
            "Average Cost": average_cost,
            "Standard Deviation": standard_deviation,
            "Analysis Date Cost": cost_on_analysis_date,
            "Alert": alert,
            "Percent Variation": percent_variation,
            "Cost Difference": cost_difference,
            "Start Date": start_date.strftime('%Y-%m-%d'),
            "End Date": end_date.strftime('%Y-%m-%d'),
            "Number of Days": total_days,
            "Analysis Date": end_date.strftime('%Y-%m-%d')
        })

    return results

 
def request_and_process(url, headers, payload, subscription_name):
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        increment_request_count()  # Incrementa o contador de requisições
        time.sleep(1)  # Pausa de 1 segundos entre as requisições
    except requests.exceptions.RequestException as e:
        handle_errors(e, f"Failed to retrieve cost data for subscription '{subscription_name}'")
    try:
        data = response.json()
        logging.debug(f"Received data: {json.dumps(data, indent=2)}")
    except json.JSONDecodeError as e:
        handle_errors(e, "JSON decode error")
    if 'properties' not in data or 'rows' not in data['properties']:
        logging.info("No Cost Found in the response data.")
        return None, 0
    return data

def analyze_costs(subscription_name, subscription_id, grouping_dimension, access_token, start_date_str=None, period=31):
    cost_management_url, payload, headers = build_cost_management_request(subscription_id, 'Dimension', grouping_dimension, access_token)
 
    start_date, end_date, _ = get_analysis_timeframe(start_date_str, period)
 
    logging.debug(f"Sending request to Cost Management API for subscription {subscription_id} with payload: {json.dumps(payload, indent=2)}")
 
    data = request_and_process(cost_management_url, headers, payload, subscription_name)
 
    if data is None:
        return "No Cost Found", 0, None
 
    costs_by_group = {}
    total_cost_analysis_date = 0
    analysis_date_str = end_date.strftime('%Y%m%d')
 
    for result in data['properties']['rows']:
        cost = float(result[0])
        date = result[1]
        group = result[2]
 
        if group not in costs_by_group:
            costs_by_group[group] = []
        costs_by_group[group].append((date, cost))
 
        if date == int(analysis_date_str):
            total_cost_analysis_date += cost
 
    results = process_costs(costs_by_group, grouping_dimension, start_date, end_date, analysis_date_str)
 
    df = pd.DataFrame(results)
 
    if df.empty:
        logging.info("No data to display.")
        return "No Cost Found", total_cost_analysis_date, None
 
    table = tabulate(df, headers='keys', tablefmt='plain', floatfmt='.3f')
    return table, total_cost_analysis_date, df
 
def analyze_costs_by_tag(subscription_name, subscription_id, tag_key, access_token, start_date_str=None, period=31):
    cost_management_url, payload, headers = build_cost_management_request(subscription_id, 'TagKey', tag_key, access_token)
 
    start_date, end_date, _ = get_analysis_timeframe(start_date_str, period)
 
    logging.debug(f"Sending request to Cost Management API for subscription {subscription_id} with payload: {json.dumps(payload, indent=2)}")
 
    data = request_and_process(cost_management_url, headers, payload, subscription_name)
 
    if data is None:
        return "No Cost Found", 0, None
 
    costs_by_tag = {}
    total_cost_analysis_date = 0
    analysis_date_str = end_date.strftime('%Y%m%d')
 
    for result in data['properties']['rows']:
        cost = float(result[0])
        date = result[1]
        tag_value = result[3]
 
        if tag_value:
            if tag_value not in costs_by_tag:
                costs_by_tag[tag_value] = []
            costs_by_tag[tag_value].append((date, cost))
 
            if date == int(analysis_date_str):
                total_cost_analysis_date += cost
 
    results = process_costs(costs_by_tag, tag_key, start_date, end_date, analysis_date_str)
 
    df = pd.DataFrame(results)
 
    if df.empty:
        logging.info("No data to display.")
        return "No Cost Found", total_cost_analysis_date, None
 
    table = tabulate(df, headers='keys', tablefmt='plain', floatfmt='.3f')
    return table, total_cost_analysis_date, df
 
def analyze_costs_by_subs(subscription_name, subscription_id, access_token, start_date_str=None, period=31):
    cost_management_url, payload, headers = build_cost_management_request(subscription_id, 'Subscription', subscription_name, access_token)
    start_date, end_date, _ = get_analysis_timeframe(start_date_str, period)
    logging.debug(f"Sending request to Cost Management API for subscription {subscription_id} with payload: {json.dumps(payload, indent=2)}")
    data = request_and_process(cost_management_url, headers, payload, subscription_name)
    if data is None:
        return {
            "Subscription": subscription_name,
            "Average Cost": 0,
            "Analysis Date Cost": 0,
            "Alert": "No",
            "Percent Variation": 0,
            "Cost Difference": 0,
            "Period of Average Calculation": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            "Number of Days": 0,
            "Analysis Date": end_date.strftime('%Y-%m-%d')
        }
    costs = []
    analysis_date_str = end_date.strftime('%Y%m%d')
    for result in data['properties']['rows']:
        cost = float(result[0])
        date = result[1]
        costs.append((date, cost))
    total_cost = sum(cost for date, cost in costs)
    total_days = len(costs)
    average_cost = total_cost / total_days if total_days > 0 else 0
    cost_on_analysis_date = next((cost for date, cost in costs if date == int(analysis_date_str)), 0)
    alert = check_alert(cost_on_analysis_date, average_cost)
    percent_variation = ((cost_on_analysis_date - average_cost) / average_cost) * 100 if average_cost != 0 else 0
    cost_difference = cost_on_analysis_date - average_cost
    return {
        "Subscription": subscription_name,
        "Average Cost": average_cost,
        "Analysis Date Cost": cost_on_analysis_date,
        "Alert": alert,
        "Percent Variation": percent_variation,
        "Cost Difference": cost_difference,
        "Period of Average Calculation": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
        "Number of Days": total_days,
        "Analysis Date": end_date.strftime('%Y-%m-%d')
    }


def analyze_subscription(subscription_name, subscription_id, analysis_type, grouping_key, access_token, alert_mode=False, start_date_str=None, period=31):
    logging.info(f"\nAnalyzing subscription: {subscription_name} with ID: {subscription_id}")
    if analysis_type.lower() == 'tag':
        result, cost_analysis_date, df = analyze_costs_by_tag(subscription_name, subscription_id, grouping_key, access_token, start_date_str, period)
    elif analysis_type.lower() == 'group':
        result, cost_analysis_date, df = analyze_costs(subscription_name, subscription_id, grouping_key, access_token, start_date_str, period)
    else:  # For subscription analysis
        result = analyze_costs_by_subs(subscription_name, subscription_id, access_token, start_date_str, period)
        df = pd.DataFrame([result])
    if df is not None:
        if alert_mode:
            alert_df = df[df['Alert'] == 'Yes']
            if not alert_df.empty:
                logging.info(f"Alerts found for {subscription_name}.")
                result = tabulate(alert_df, headers='keys', tablefmt='plain', floatfmt='.3f')
                return subscription_name, alert_df, result
            else:
                logging.info(f"No alerts found for {subscription_name}.")
                return subscription_name, None, "No alerts found"
        else:
            result = tabulate(df, headers='keys', tablefmt='plain', floatfmt='.3f')
            return subscription_name, df, result
    else:
        return subscription_name, None, "No data found"


def save_execution_result(status, subscription_results, common_prefix, grouping_key):
    try:
        # Lista para armazenar todos os dataframes
        df_list = []
        # Itera sobre os resultados de cada subscrição
        for subscription_name, df in subscription_results.items():
            df['Subscrição'] = subscription_name
            df_list.append(df)
        # Concatena todos os dataframes em um único dataframe
        combined_df = pd.concat(df_list, ignore_index=True)
        # Reorganiza as colunas para ter 'Subscrição' como a primeira coluna
        cols = ['Subscrição'] + [col for col in combined_df.columns if col != 'Subscrição']

        # Remover a coluna antiga 'Period of Average Calculation', se existir
        if 'Period of Average Calculation' in combined_df.columns:
            combined_df = combined_df.drop(columns=['Period of Average Calculation'])

        combined_df = combined_df[cols]

        # Recupera a data de análise da primeira linha do DataFrame
        if 'Analysis Date' in combined_df.columns:
            analysis_date = combined_df['Analysis Date'].iloc[0]
        else:
            analysis_date = "unknown_date"

        # Define o nome do arquivo com a data de análise
        filename = f"{common_prefix}_{grouping_key}_{analysis_date}.xlsx"

        # Salva o dataframe combinado em um novo arquivo Excel
        combined_df.to_excel(filename, index=False)
        logging.info(f"Results saved to {filename}")
    except Exception as e:
        logging.error(f"Failed to save results: {e}")

