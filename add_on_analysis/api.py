import requests

def get_company_data(vat):
    url = "https://www.staatsbladmonitor.be/sbmapi.json"

    params = {
        "accountid": "3363674",
        "apikey": "bb084cde-c287-410f-9dd5-49f6c233af4b",
        "vat": vat,
        "fin": 1,
    }
    
    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise Exception(f"API call failed with status code {response.status_code}")
    
    print(response.url)
    response = response.json()
    print(response)
    
    fin_year_1 = {
        'enddate' : response['data']['annualaccounts'][0]['enddate'],
        'pdf' : response['data']['annualaccounts'][0]['pdf'],
    }
    
    for value in response['data']['annualaccounts'][0]['keyvalues']:
        fin_year_1[value['code']] = value['value']
        
    fin_year_2 = {
        'enddate' : response['data']['annualaccounts'][1]['enddate'],
        'pdf' : response['data']['annualaccounts'][1]['pdf'],
    }
    
    for value in response['data']['annualaccounts'][1]['keyvalues']:
        fin_year_2[value['code']] = value['value']
        
    fin_year_3 = {
        'enddate' : response['data']['annualaccounts'][2]['enddate'],
        'pdf' : response['data']['annualaccounts'][2]['pdf'],
    }
    
    for value in response['data']['annualaccounts'][2]['keyvalues']:
        fin_year_3[value['code']] = value['value']
        
    fin_year_4 = {
        'enddate' : response['data']['annualaccounts'][3]['enddate'],
        'pdf' : response['data']['annualaccounts'][3]['pdf'],
    }
    
    for value in response['data']['annualaccounts'][3]['keyvalues']:
        fin_year_4[value['code']] = value['value']
        
    company_details = {
        'startdate' : response['data']['company']['startdate'],
        'name' : response['data']['company']['denomination'],
        'form' : response['data']['company']['juridicalform'],
        'street' : response['data']['mainaddress']['street'],
        'number' : response['data']['mainaddress']['housenumber'],
        'zipcode' : response['data']['mainaddress']['zipcode'],
        'city' : response['data']['mainaddress']['city'],
        'activities' : response['data']['activities'],
        'fin' : [fin_year_1, fin_year_2, fin_year_3, fin_year_4]
    }
    
    return company_details