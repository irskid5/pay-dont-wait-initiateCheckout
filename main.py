import simplejson as json
import psycopg2
import traceback
import decimal
from datetime import datetime
import requests

class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()

        return json.JSONEncoder.default(self, o)
        
def item_to_dict(description, product_code, quantity, unit_cost):

    return {"url": "", "description": description, "product_code": product_code, "unit_cost": "{:.2f}".format(unit_cost), "quantity": str(quantity)}

    

def lambda_handler(event, context):
    # TODO implement
    print("Event:")
    print(event)
    try:
    
        #import body json
        data = json.loads(event["body"])

        #connect to the database
        connection = psycopg2.connect(user="pmok3",
                                  password="paydontwait",
                                  host="database117.ci9cgiakdb8y.us-east-2.rds.amazonaws.com",
                                  port="5432",
                                  database="paydontwaitdatabase")
        
        cursor = connection.cursor()
        
        #execute query and sanitize against SQL injection
        cursor.execute("create temporary view info as SELECT service_id, day_of_service, service_started FROM Service Where table_id = %s ORDER BY day_of_service DESC, service_started DESC LIMIT 1; create temporary view receipt as SELECT info.service_id as service_id, day_of_service, service_started, name as server, table_id, item_desc as description, quantity, price as amount, item_id FROM info NATURAL JOIN Service NATURAL JOIN Servers NATURAL JOIN Suborder NATURAL JOIN Items ORDER BY item_desc ASC; create temporary view total as SELECT sum(amount*quantity) as total FROM receipt; SELECT * FROM receipt, total; ",(data["table_id"],))
           
        receipt = cursor.fetchall()

        #print(receipt)
        
        total = receipt[1][9]
        service_id, day_of_service, service_started, server, table_id = receipt[1][0:5]
        
        items = {}
        for i in range(1,len(receipt)):
            #items[description] = [quantity, amount, item_id]
            items[receipt[i][5]] = {"maxNumber": receipt[i][6], "cost": float(receipt[i][7])}
            
        #print("Items:")
        #print(items)
        
        #close cursor, connection
        cursor.close()
        connection.close()
        
        #Checking if the items are part of the receipt
        new_items = data["items"]
        for item in new_items.keys():
            
            #print(item)
            #print(item not in items.keys())
            #print(new_items[item]['number'] > items[item]['maxNumber'])
            #print(new_items[item]['number'] < 0)
            #print(new_items[item]['maxNumber'] != items[item]['maxNumber'])
            #print(new_items[item]['cost'] != items[item]['cost'])
            #print(type(new_items[item]['cost']))
            if ((item not in items.keys()) or (new_items[item]['number'] > items[item]['maxNumber']) or (new_items[item]['number'] < 0) or (new_items[item]['maxNumber'] != items[item]['maxNumber']) or (new_items[item]['cost'] != items[item]['cost'])):
            
                return {
                   'statusCode': 500,
                   'headers': {
                   "x-custom-header" : "my custom header value",
                   "Access-Control-Allow-Origin": "*"
                   },
                   'body': json.dumps({"success": False, "error": "Exception"})
                   }
            else:
                continue
    
        #Making an array of item objects {"items": [{item1}, {item2}, ...] using partial item array
        item_list = []
        sub_total = 0
        for item in new_items.keys(): 
            if (new_items[item]["number"] > 0):
                item_list.append(item_to_dict(item, "", new_items[item]["number"], items[item]["cost"]))
                sub_total += new_items[item]["number"] * items[item]["cost"]
		
	# create shopping cart
	# enter tax stuff
        tax_rate = 0.13
        tax_description = "HST"
        tax_amount = sub_total * tax_rate
        post_tax_total = sub_total + tax_amount
        tax_obj = {"amount": "{:.2f}".format(tax_amount), "description": tax_description, "rate": str(int(tax_rate*100))+"%"}

	# enter tip stuff
        tip_amount = data["tipPercent"] * post_tax_total
        tip_desc = "Tip - " + str(int(data["tipPercent"]*100)) + " percent"
        item_list.append(item_to_dict(tip_desc, "", 1, tip_amount))

        shopping_cart = {"items": item_list, \
                         "subtotal": "{:.2f}".format(sub_total), \
                         "tax": tax_obj}
        
        #print(shopping_cart)
        #Connect to moneris checkout
        moneris_url = "https://gatewayt.moneris.com/chkt/request/request.php"
        
        #Preload and send store id, API token, checkout ID, shopping cart
        #Store ID, API Token, Checkout ID hardcoded
        
        #Make preload object
        preload = json.dumps({"store_id": "monca04308", \
                                "api_token": "y6Hx5c2KyAIqkDlPeepY", \
                                "checkout_id": "chkt2E24504308", \
                                "txn_total": "{:.2f}".format(post_tax_total+tip_amount), \
                                "environment": "qa", \
                                "action": "preload", \
                                "cart": shopping_cart}) 
        
        
        #Create a POST request to moneris checkout
        r = requests.post(url = moneris_url, data = preload)
    
        r.raise_for_status()
        rData = r.json()
        if (rData["response"]["success"] == "true"):
            return {
                'statusCode': 200,
                'headers': {
                    "x-custom-header" : "my custom header value",
                    "Access-Control-Allow-Origin": "*"
                },
                'body': json.dumps({"success": True, "ticket": rData["response"]["ticket"]})
            }

        return {
            'statusCode': 200,
            'headers': {
                "x-custom-header" : "my custom header value",
                "Access-Control-Allow-Origin": "*"
            },
            'body': json.dumps({"success": False, "error": "Bad Request"})
        } 
    except Exception as err:
        print("Exception: " + str(err))
        print(traceback.format_exc())
        return {
            'statusCode': 500,
            'headers': {
                "x-custom-header" : "my custom header value",
                "Access-Control-Allow-Origin": "*"
            },
            'body': json.dumps({"success": False, "error": "Exception"})
        }
        
    return {
        'statusCode': 500,
        'headers': {
            "x-custom-header" : "my custom header value",
            "Access-Control-Allow-Origin": "*"
        },
        'body': json.dumps({"success": False, "error": "unknown"})
    }
