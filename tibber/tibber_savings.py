#!/cygdrive/c/Python311/python
import calendar
import datetime
import json
import os
import subprocess
import sys
import time

################################################################################################################################################################
### Usage
################################################################################################################################################################

def usage(info):
    print()
    print("################################################################################")
    print("### Usage: {}".format(info))
    print("################################################################################")
    print()
    print("{} [-t|--tibber TIBBER_BEARER] [-c|--tibber-notification-copy TIBBER_BEARER] [-n|--tibber-notification TIBBER_BEARER] [-f'|--file BEARER_FILE] [-s|--slack SKACK_HOOK] [-i|--show_info] [--analyze_bill]".format(sys.argv[0]))
    print()
    print("Example:")
    print("{} -t TIBBER-TOKEN-123456789012345678901234567890".format(sys.argv[0]))
    print()
    print("crontab example: ")
    print("37 13 * * * cd <PATH_TO_SCRIPT>; ./tibber_savings.py -t <TIBBER_BEARER> ./tibber_savings.log 2>&1")
    exit()

################################################################################################################################################################
### Initial valiabled
################################################################################################################################################################

tibber_bearer_notification = ""
tibber_bearer_notification_copy = ""
tibber_file = ""
show_info = False
analyze_bill = False
tibber_bearers_raw = []
tibber_bearers = []
slack_hooks = []
start_time = "18:00"
end_time = "10:00"
start_time_daytime = "08:00"
end_time_daytime = "23:00"
daytime_hours = False

print("################################################################################")
print("### Handle arguments")
print("################################################################################")
arg=1
while arg < len(sys.argv):
    argument = sys.argv[arg]
    if argument == '-t' or argument == '--tibber':
        print("Parameter (Tibber bearer)                    : '{}'".format(sys.argv[arg+1]))
        tibber_bearers_raw.append(sys.argv[arg+1])
    elif argument == '-c' or argument == '--tibber-notification-copy':
        tibber_bearer_notification_copy = sys.argv[arg+1]
        print("Parameter (Tibber bearer notification copy)  : '{}'".format(tibber_bearer_notification_copy))
    elif argument == '-n' or argument == '--tibber-notification':
        tibber_bearer_notification = sys.argv[arg+1]
        print("Parameter (Tibber bearer notification)       : '{}'".format(tibber_bearer_notification))
    elif argument == '-s' or argument == '--slack':
        slack_hooks.append(sys.argv[arg+1])
        print("Parameter (Slack hook)                       : '{}'".format(sys.argv[arg+1]))
    elif argument == '-f' or argument == '--file':
        tibber_file = sys.argv[arg+1]
        print("Parameter (Tibber bearer file)               : '{}'".format(tibber_file))
    elif argument == '-i' or argument == '--show_info':
        show_info = True
        arg -= 1
        print("Parameter (Show info)                        : 'True'")
    elif argument == '--analyze_bill':
        analyze_bill = True
        print("Parameter (Analyze bill)                     : 'True'")
    else:
        usage("Unknown argument = '{}'".format(argument))
    arg += 2
print()

################################################################################################################################################################
### Get Tibber info
################################################################################################################################################################

def tibber_get_data(bearer, request, show_result = False):
    tibber_api_auth="-sH \"Authorization: Bearer {}\"".format(bearer)
    tibber_api_content="-H \"Content-Type: application/json\""
    tibber_api_command="\"query\""
    tibber_api_value="\"{}\"".format(request)
    tibber_api_url="https://api.tibber.com/v1-beta/gql"
    command="curl {} {} -d '{{ {} : {} }}' {}".format(tibber_api_auth, tibber_api_content, tibber_api_command, tibber_api_value, tibber_api_url)
    if show_result:
        print("Command:\n{}\n".format(command))
        print()

    proc = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    (out, err) = proc.communicate()
    proc.wait()
    if show_result:
        print("Tibber response:\n{}".format(str(out, "utf-8")))
        print()

    # print("Tibber response:\n{}".format(json.dumps(json.loads(out), indent=2), "utf-8"))
    # print()

    return(json.loads(out))

################################################################################################################################################################
### Populate tibber bearer array
################################################################################################################################################################

if tibber_file != "":
    try:
        my_file = open(tibber_file, 'r')
        tibber_bearers_raw = my_file.readlines()
        my_file.close()
    except:
        usage("Could not open file '{}'".format(tibber_file))

# print("tibber_bearers_raw: {}".format(tibber_bearers_raw))

for file_line in tibber_bearers_raw:
    if file_line[0:1] == "#" or len(file_line.strip()) < 43:
        continue
    file_arr = file_line.strip().split()
    # print(file_arr)
    # print("tibber_bearer : {}".format(file_arr[0]))
    tibber_bearers.append(file_arr[0])
    if len(file_arr) == 2:
        slack_token = file_arr[1]
        # print("slack_token   : {}".format(slack_token))
        slack_hooks.append(slack_token)
    else:
        slack_hooks.append(None)
    # print()

################################################################################################################################################################
### Analyze bill
################################################################################################################################################################
def add_months(sourcedate, months):
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, calendar.monthrange(year,month)[1])
    return datetime.date(year, month, day)

if analyze_bill == True:
    print("### Analyze bill")
    print()

    # Get end of all checks
    timestamp_latest = datetime.datetime.now().strftime("%Y-%m-01T00:00:00")
    # print("timestamp_latest : " + timestamp_latest)
    # print()

    data_index = 0
    for bearer_index in range(0, len(tibber_bearers)):
        tibber_response = tibber_get_data(tibber_bearers[bearer_index], "{ viewer { homes { address { address1 address2 address3 postalCode city country latitude longitude } consumption(resolution: HOURLY, last: 7000) { nodes { from to cost unitPrice unitPriceVAT consumption consumptionUnit } } } } }")

        for home in tibber_response["data"]["viewer"]["homes"]:
            previous_month  = 1 # januari
            timestamp_end = timestamp_latest

            value_address1 = home["address"]["address1"]
            print("# {}".format(value_address1))

            while home["consumption"] != None:
                timestamp_end_date   = datetime.datetime.strptime(timestamp_end, "%Y-%m-%dT%H:%M:%S")
                timestamp_start      = str(add_months(timestamp_end_date, -1)) + "T00:00:00"
                timestamp_start_date = datetime.datetime.strptime(timestamp_start, "%Y-%m-%dT%H:%M:%S")
                # print("{} - {}".format(timestamp_start, timestamp_end))

                index_start = 0
                index_end = 0
                count_unitPrice = 0
                sum_unitPrice = 0
                count_cost = 0
                sum_cost = 0
                count_consumption = 0
                sum_consumption = 0
                check_average = False

                # print(len(home["consumption"]["nodes"]))
                # if len(home["consumption"]["nodes"]) == 0:
                    # break

                for node_index in range(0, len(home["consumption"]["nodes"])):
                    #print("node_index: {}".format(node_index))
                    node = home["consumption"]["nodes"][node_index]

                    value_from              = node["from"]
                    value_to                = node["to"]
                    value_unitPrice         = node["unitPrice"]
                    value_cost              = node["cost"]
                    value_consumption       = node["consumption"]
                    value_consumptionUnit   = node["consumptionUnit"]

                    #print("Node: {} {}".format(node, value_from))
                    if timestamp_start in value_from:
                        index_start = node_index
                        # print("Index start : {:5d}  From: {}".format(index_start, value_from))
                        check_average = True

                    if check_average:
                        count_unitPrice += 1
                        sum_unitPrice += value_unitPrice
                        count_cost += 1
                        sum_cost += value_cost
                        count_consumption += 1
                        sum_consumption += value_consumption
                        #print("{:20s} - {:5.2f}, unitPrice: {:4d},{:7.2f}, cost: {:4d},{:7.2f}".format(value_from, value_unitPrice, count_unitPrice, sum_unitPrice, count_cost, sum_cost))

                    if timestamp_end in value_to:
                        index_end = node_index
                        # print("Index end   : {:5d}  To:   {}".format(index_end, value_to))
                        check_average = False
                        break

                if count_unitPrice == 0:
                    break
                #print("index_start: {}, index_end: {}, count_unitPrice: {}". format(index_start, index_end, count_unitPrice))
                average_price = sum_unitPrice / count_unitPrice
                average_cost = sum_cost / count_cost
                average_consumption = sum_consumption / count_consumption

                # data.append([])
                # data[data_index].append(value_address1)
                # data[data_index].append(average)
                # print(len(data))
                # print ("{:2d} - {:30s} - Average price       : {:8.2f} / {:4d} = {:.2f}".format(data_index, value_address1, sum_unitPrice,   count_unitPrice,   average_price))
                # print ("{:2d} - {:30s} - Average cost        : {:8.2f} / {:4d} = {:.2f}".format(data_index, value_address1, sum_cost,        count_cost,        average_cost))
                # print ("{:2d} - {:30s} - Average consumption : {:8.2f} / {:4d} = {:.2f}".format(data_index, value_address1, sum_consumption, count_consumption, average_consumption))
                # print()
                period_start = str(datetime.datetime.strptime(timestamp_start, "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m"))
                print("{}: {:7.2f} {} a {:6.2f} ({:6.2f}) öre/{} = {:8.2f} ({:8.2f}) - average: {:6.2f} ({:6.2f}) öre/{} - diff: {:6.2f}".format(
                    period_start, sum_consumption, value_consumptionUnit, 100*sum_cost/sum_consumption/1.25, 100*sum_cost/sum_consumption, value_consumptionUnit, sum_cost/1.25, sum_cost, 100*average_price/1.25, 100*average_price, value_consumptionUnit, 100*sum_cost/sum_consumption - 100 * average_price))
                # print()

                # data_index += 1
                # print("{:20s} - {:5.2f}, unitPrice: {:7.2f} ({:d}), cost: {:7.2f} ({:d})".format(value_from, value_unitPrice, sum_unitPrice, count_unitPrice, sum_cost, count_cost))
                timestamp_end = timestamp_start

            print()

    print("Exit after Analyze bill")
    exit()

################################################################################################################################################################
### Get bearer info
################################################################################################################################################################
if show_info == True:
    print("### Bearer info")
    for bearer_index in range(0, len(tibber_bearers)):
        tibber_response = tibber_get_data(tibber_bearers[bearer_index], "{viewer {homes {address {address1 city} owner {firstName lastName contactInfo { email mobile } } currentSubscription { status } } } }")
        for home in tibber_response["data"]["viewer"]["homes"]:
            if home["currentSubscription"] == None:
                status = "None"
            else:
                status = home["currentSubscription"]["status"]
            print("{:15s} {:15s} {:30s} {:15s} {:40s} {:25s} {:15s} {:45s} {}".format(home["owner"]["firstName"], home["owner"]["lastName"], home["address"]["address1"], home["address"]["city"], home["owner"]["contactInfo"]["email"], str(home["owner"]["contactInfo"]["mobile"]), status, tibber_bearers[bearer_index], slack_hooks[bearer_index]))
    print()
    print("Exit after showing info")
    exit()

if len(tibber_bearers) == 0:
    usage("No valid Tibber bearer found!")

################################################################################################################################################################
### Parse all bearers
################################################################################################################################################################

for bearer_index in range(0, len(tibber_bearers)):
    print("bearer_index               : '{}'".format(bearer_index))
    print("Period start               : '{}'".format(start_time))
    print("Period end                 : '{}'".format(end_time))
    print("Tibber bearer              : '{}'".format(tibber_bearers[bearer_index]))
    print("Tibber bearer notification : '{}'".format(tibber_bearer_notification))
    print("Slack API hook             : '{}'".format(slack_hooks[bearer_index]))
    print()

    tibber_response = tibber_get_data(tibber_bearers[bearer_index], "{ viewer { homes { address { address1 address2 address3 postalCode city country latitude longitude } currentSubscription { priceInfo { today { startsAt total } tomorrow { startsAt total } } } } }}")
    if "Context creation failed: invalid token" in str(tibber_response):
        usage("Invalid token")

    print("### Adresser ({} st)".format(len(tibber_response["data"]["viewer"]["homes"])))
    for home in tibber_response["data"]["viewer"]["homes"]:
        print(home["address"]["address1"])
    print()

    ################################################################################################################################################################
    ### Handle data
    ################################################################################################################################################################

    print("################################################################################")
    print("##### Handle data")
    print("################################################################################")
    for home in tibber_response["data"]["viewer"]["homes"]:
        tibber_address = home["address"]["address1"]
        tibber_city = home["address"]["city"]
        #print("### Adress: {}, {}".format(tibber_address, tibber_city))
        #print()

        if home["currentSubscription"] == None:
            print("Avtal saknas")
            print()
            continue

        length_tomorrow = len(home["currentSubscription"]["priceInfo"]["tomorrow"])
        print("Length of tomorrow: {}".format(length_tomorrow))

        if (length_tomorrow == 0):
            daytime_hours = True
            # out='{"data":{"viewer":{"homes":[{"address":{"address1":"ABC 1","address2":null,"address3":null,"postalCode":"12345","city":"A-stad","country":"SE","latitude":"58.8888888","longitude":"16.6666666"},"currentSubscription":{"priceInfo":{"today":[{"startsAt":"2023-02-20T00:00:00.000+01:00","total":0.8675},{"startsAt":"2023-02-20T01:00:00.000+01:00","total":0.7473},{"startsAt":"2023-02-20T02:00:00.000+01:00","total":0.7153},{"startsAt":"2023-02-20T03:00:00.000+01:00","total":0.5815},{"startsAt":"2023-02-20T04:00:00.000+01:00","total":0.5248},{"startsAt":"2023-02-20T05:00:00.000+01:00","total":0.5948},{"startsAt":"2023-02-20T06:00:00.000+01:00","total":0.6525},{"startsAt":"2023-02-20T07:00:00.000+01:00","total":0.7855},{"startsAt":"2023-02-20T08:00:00.000+01:00","total":0.8753},{"startsAt":"2023-02-20T09:00:00.000+01:00","total":0.7988},{"startsAt":"2023-02-20T10:00:00.000+01:00","total":0.7043},{"startsAt":"2023-02-20T11:00:00.000+01:00","total":0.6006},{"startsAt":"2023-02-20T12:00:00.000+01:00","total":0.6041},{"startsAt":"2023-02-20T13:00:00.000+01:00","total":0.5953},{"startsAt":"2023-02-20T14:00:00.000+01:00","total":0.6981},{"startsAt":"2023-02-20T15:00:00.000+01:00","total":0.8319},{"startsAt":"2023-02-20T16:00:00.000+01:00","total":0.8146},{"startsAt":"2023-02-20T17:00:00.000+01:00","total":0.9248},{"startsAt":"2023-02-20T18:00:00.000+01:00","total":0.9554},{"startsAt":"2023-02-20T19:00:00.000+01:00","total":0.8995},{"startsAt":"2023-02-20T20:00:00.000+01:00","total":0.8598},{"startsAt":"2023-02-20T21:00:00.000+01:00","total":0.8153},{"startsAt":"2023-02-20T22:00:00.000+01:00","total":0.7654},{"startsAt":"2023-02-20T23:00:00.000+01:00","total":0.7188}],"tomorrow":[{"startsAt":"2023-02-21T00:00:00.000+01:00","total":0.8675},{"startsAt":"2023-02-21T01:00:00.000+01:00","total":0.7473},{"startsAt":"2023-02-21T02:00:00.000+01:00","total":0.7153},{"startsAt":"2023-02-21T03:00:00.000+01:00","total":0.5815},{"startsAt":"2023-02-21T04:00:00.000+01:00","total":0.5248},{"startsAt":"2023-02-21T05:00:00.000+01:00","total":0.5948},{"startsAt":"2023-02-21T06:00:00.000+01:00","total":0.6525},{"startsAt":"2023-02-21T07:00:00.000+01:00","total":0.7855},{"startsAt":"2023-02-21T08:00:00.000+01:00","total":0.8753},{"startsAt":"2023-02-21T09:00:00.000+01:00","total":0.7988},{"startsAt":"2023-02-21T10:00:00.000+01:00","total":0.7043},{"startsAt":"2023-02-21T11:00:00.000+01:00","total":0.6006},{"startsAt":"2023-02-21T12:00:00.000+01:00","total":0.6041},{"startsAt":"2023-02-21T13:00:00.000+01:00","total":0.5953},{"startsAt":"2023-02-21T14:00:00.000+01:00","total":0.6981},{"startsAt":"2023-02-21T15:00:00.000+01:00","total":0.8319},{"startsAt":"2023-02-21T16:00:00.000+01:00","total":0.8146},{"startsAt":"2023-02-21T17:00:00.000+01:00","total":0.9248},{"startsAt":"2023-02-21T18:00:00.000+01:00","total":0.9554},{"startsAt":"2023-02-21T19:00:00.000+01:00","total":0.8995},{"startsAt":"2023-02-21T20:00:00.000+01:00","total":0.8598},{"startsAt":"2023-02-21T21:00:00.000+01:00","total":0.8153},{"startsAt":"2023-02-21T22:00:00.000+01:00","total":0.7654},{"startsAt":"2023-02-21T23:00:00.000+01:00","total":0.7188}]}}},{"address":{"address1":"XYZ 2","address2":null,"address3":null,"postalCode":"22222","city":"X-stad","country":"SE","latitude":"55.5555555","longitude":"13.3333333"},"currentSubscription":{"priceInfo":{"tomorrow":[{"startsAt":"2023-02-20T00:00:00.000+01:00","total":0.8675},{"startsAt":"2023-02-20T01:00:00.000+01:00","total":0.7473},{"startsAt":"2023-02-20T02:00:00.000+01:00","total":0.7153},{"startsAt":"2023-02-20T03:00:00.000+01:00","total":0.5815},{"startsAt":"2023-02-20T04:00:00.000+01:00","total":0.5248},{"startsAt":"2023-02-20T05:00:00.000+01:00","total":0.5948},{"startsAt":"2023-02-20T06:00:00.000+01:00","total":0.6525},{"startsAt":"2023-02-20T07:00:00.000+01:00","total":0.7855},{"startsAt":"2023-02-20T08:00:00.000+01:00","total":0.8753},{"startsAt":"2023-02-20T09:00:00.000+01:00","total":0.7988},{"startsAt":"2023-02-20T10:00:00.000+01:00","total":0.7043},{"startsAt":"2023-02-20T11:00:00.000+01:00","total":0.6006},{"startsAt":"2023-02-20T12:00:00.000+01:00","total":0.6041},{"startsAt":"2023-02-20T13:00:00.000+01:00","total":0.5953},{"startsAt":"2023-02-20T14:00:00.000+01:00","total":0.6981},{"startsAt":"2023-02-20T15:00:00.000+01:00","total":0.8319},{"startsAt":"2023-02-20T16:00:00.000+01:00","total":0.8146},{"startsAt":"2023-02-20T17:00:00.000+01:00","total":0.9248},{"startsAt":"2023-02-20T18:00:00.000+01:00","total":0.9554},{"startsAt":"2023-02-20T19:00:00.000+01:00","total":0.8995},{"startsAt":"2023-02-20T20:00:00.000+01:00","total":0.8598},{"startsAt":"2023-02-20T21:00:00.000+01:00","total":0.8153},{"startsAt":"2023-02-20T22:00:00.000+01:00","total":0.7654},{"startsAt":"2023-02-20T23:00:00.000+01:00","total":0.7188}],"tomorrow":[{"startsAt":"2023-02-21T00:00:00.000+01:00","total":0.8245},{"startsAt":"2023-02-21T01:00:00.000+01:00","total":0.7049},{"startsAt":"2023-02-21T02:00:00.000+01:00","total":0.6473},{"startsAt":"2023-02-21T03:00:00.000+01:00","total":0.5396},{"startsAt":"2023-02-21T04:00:00.000+01:00","total":0.4832},{"startsAt":"2023-02-21T05:00:00.000+01:00","total":0.5529},{"startsAt":"2023-02-21T06:00:00.000+01:00","total":0.6104},{"startsAt":"2023-02-21T07:00:00.000+01:00","total":0.7429},{"startsAt":"2023-02-21T08:00:00.000+01:00","total":0.8323},{"startsAt":"2023-02-21T09:00:00.000+01:00","total":0.7561},{"startsAt":"2023-02-21T10:00:00.000+01:00","total":0.6562},{"startsAt":"2023-02-21T11:00:00.000+01:00","total":0.5587},{"startsAt":"2023-02-21T12:00:00.000+01:00","total":0.5622},{"startsAt":"2023-02-21T13:00:00.000+01:00","total":0.5534},{"startsAt":"2023-02-21T14:00:00.000+01:00","total":0.6558},{"startsAt":"2023-02-21T15:00:00.000+01:00","total":0.7892},{"startsAt":"2023-02-21T16:00:00.000+01:00","total":0.7719},{"startsAt":"2023-02-21T17:00:00.000+01:00","total":0.8817},{"startsAt":"2023-02-21T18:00:00.000+01:00","total":0.9122},{"startsAt":"2023-02-21T19:00:00.000+01:00","total":0.8564},{"startsAt":"2023-02-21T20:00:00.000+01:00","total":0.8169},{"startsAt":"2023-02-21T21:00:00.000+01:00","total":0.7726},{"startsAt":"2023-02-21T22:00:00.000+01:00","total":0.7228},{"startsAt":"2023-02-21T23:00:00.000+01:00","total":0.6764}]}}}]}}}'
            # print("Too early, use daytime data:\n{}".format(out))
            print("Too early, use daytime hours")
            start_time = start_time_daytime
            end_time = end_time_daytime
            # print()
            # tibber_response = json.loads(out)
            # home = tibber_response["data"]["viewer"]["homes"][0]
            # #length_tomorrow = len(tibber_response["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["tomorrow"])
            # length_tomorrow = len(home["currentSubscription"]["priceInfo"]["tomorrow"])
            # print ("Length of tomorrow: {}".format(length_tomorrow))
        print()

        ################################################################################################################################################################

        arr_timestamps = []
        arr_prices = []
        index_start = 0
        hour_index = 0
        for day in ["today", "tomorrow"]:
            for info_hour in home["currentSubscription"]["priceInfo"][day]:
                #print("Adding ({}, ({:5.2f}) to arrays[{}],".format(info_hour["startsAt"], info_hour["total"], hour_index), end = '')
                arr_timestamps.append(info_hour["startsAt"])
                arr_prices.append(info_hour["total"])
                if (index_start == 0 and start_time in arr_timestamps[hour_index] ):
                    index_start = hour_index
                    #print(" <- start", end = '')
                hour_index += 1
                #print()
        #print()

        ################################################################################################################################################################

        message_to_post = "Adress: {}, {}".format(tibber_address, tibber_city, end="")
        for duration in range(4, 2, -1):
            print("### Adress: {}, {}. Duration: {}. ".format(tibber_address, tibber_city, duration), end='')
            average_lowest=100.0
            average_highest=0.0

            # Find index for end
            index_end=0
            for hour_index in range(index_start + 1, len(arr_timestamps)):
                if (end_time in arr_timestamps[hour_index]):
                    index_end = hour_index - duration+1
                    break
            print("index: {}-{}".format(index_start, index_end))

            # This should never occur
            if (index_end == 0):
                print("Too early!")
                exit()

            #print("len(arr_timestamps): {}".format(len(arr_timestamps)))

            for hour_index in range(index_start, len(arr_timestamps)):
                print("Index: {:2d}  Timestamp: {}  Hours prices: {:2d} ({:5.2f})".format(hour_index, arr_timestamps[hour_index], hour_index, arr_prices[hour_index]), end='')
                average = arr_prices[hour_index]

                if hour_index == index_end + duration:
                    print()
                    break
                if hour_index >= index_end:
                    print()
                    continue

                for hour_iter in range (hour_index+1, hour_index + duration):
                    print(" {:2d} ({:5.2f})".format(hour_iter, arr_prices[hour_iter]), end='')
                    average += arr_prices[hour_iter]
                average /= duration

                print("  Average: " + str("{:5.2f}".format(average)), end='')

                if (average < average_lowest):
                    average_lowest = average
                    average_timestamp_start = arr_timestamps[hour_index]
                    average_timestamp_end = arr_timestamps[hour_index+duration]
                    print("  Lowest", end='')
                    if (arr_prices[hour_index] <= arr_prices[hour_index + duration - 1]):
                        average_timestamp_info = "{}h starta kl. {} ({:.2f} kr/kWh)".format(
                            str(duration),
                            str(datetime.datetime.strptime(average_timestamp_start, "%Y-%m-%dT%H:%M:%S.%f%z").strftime("%H:%M")),
                            average_lowest)
                    else:
                        average_timestamp_info = "{}h avsluta kl. {} ({:.2f} kr/kWh)".format(
                            str(duration),
                            str(datetime.datetime.strptime(average_timestamp_end,   "%Y-%m-%dT%H:%M:%S.%f%z").strftime("%H:%M")),
                            average_lowest)
                else:
                    print("        ", end='')

                if (hour_index == index_start):
                    average_timestamp_compare = "Jmf kl. {}-{} ({:.2f} kr/kWh)".format(
                        str(datetime.datetime.strptime(arr_timestamps[hour_index],          "%Y-%m-%dT%H:%M:%S.%f%z").strftime("%H:%M")),
                        str(datetime.datetime.strptime(arr_timestamps[hour_index+duration], "%Y-%m-%dT%H:%M:%S.%f%z").strftime("%H:%M")),
                        average)

                if (average > average_highest):
                    average_highest = average
                    average_timestamp_start_highest = arr_timestamps[hour_index]
                    average_timestamp_end_highest   = arr_timestamps[hour_index+duration]
                    print("  Highest")
                    average_timestamp_info_highest = "Max kl. {}-{} ({:.2f} kr/kWh)".format(
                        str(datetime.datetime.strptime(average_timestamp_start_highest, "%Y-%m-%dT%H:%M:%S.%f%z").strftime("%H:%M")),
                        str(datetime.datetime.strptime(average_timestamp_end_highest, "%Y-%m-%dT%H:%M:%S.%f%z").strftime("%H:%M")),
                        average_highest)
                else:
                    print()

            # print()
            # print("Duration       : " + str(duration))
            # print("Start          : " + str(datetime.datetime.strptime(average_timestamp_start, "%Y-%m-%dT%H:%M:%S.%f%z").strftime("%Y-%m-%d %H:%M %A")))
            # print("End            : " + str(datetime.datetime.strptime(average_timestamp_end,   "%Y-%m-%dT%H:%M:%S.%f%z").strftime("%Y-%m-%d %H:%M %A")))
            # print("Average        : " + str("{:.2f}".format(average_lowest)))
            # print()
            print("Message: {}". format(average_timestamp_info))
            message_to_post += "\n\n" + average_timestamp_info + "\n" + average_timestamp_compare + "\n" + average_timestamp_info_highest
            print()

        print("################################################################################")
        print("### Message to post:")
        print("################################################################################")
        print("{}\n".format(message_to_post))

        ################################################################################################################################################################

        print("################################################################################")
        print("### Post to Tibber")
        print("################################################################################")

        tibber_title = "Electricity price savings ({}-{})".format(start_time, end_time)
        if (daytime_hours == True):
            tibber_title += " (Daytime hours)"

        tibber_message_to_post = message_to_post.replace("\n", "\\\\\\\\n")
        tibber_post = "mutation{ sendPushNotification(input: { title: \\\"" + tibber_title + "\\\", message: \\\"" + tibber_message_to_post + "\\\", screenToOpen: HOME }){successful pushedToNumberOfDevices}}"

        # Sent notification to original OR notifixation receiver
        if tibber_bearer_notification == "":
            print("Send notification to tibber receiver")
            tibber_response = tibber_get_data(tibber_bearers[bearer_index], tibber_post, True)
        else:
            print("Send notification to notification receiver")
            tibber_response = tibber_get_data(tibber_bearer_notification, tibber_post, True)

        # Sent notification copy
        if tibber_bearer_notification_copy != "" and tibber_bearer_notification_copy != tibber_bearers[bearer_index]:
            tibber_response = tibber_get_data(tibber_bearer_notification_copy, tibber_post, True)

        time.sleep(2.0)

    ################################################################################################################################################################

    # print("slack_hooks[0]            : {}".format(slack_hooks[0]))
    # print("bearer_index              : {}".format(bearer_index))
    # print("slack_hooks[bearer_index] : {}".format(slack_hooks[bearer_index]))
    if slack_hooks[bearer_index] != None:
        print("################################################################################")
        print("### Post to slack: {}".format(slack_hooks[bearer_index]))
        print("################################################################################")
        if (daytime_hours == True):
            slack_message_to_post = ("(Daytime hours)\n" + message_to_post).replace("\n", "\\\\n")
        else:
            slack_message_to_post = message_to_post.replace("\n", "\\\\n")

        slack_api_content="-H \"Content-Type: application/json\""
        slack_api_value = slack_message_to_post
        slack_api_url="https://hooks.slack.com/services/{}".format(slack_hooks[bearer_index])

        command="curl -X POST {} --data '{{ \"{}\" : \"{}\" }}' {}".format(slack_api_content, "text", slack_api_value, slack_api_url)
        #print("Command:\n{}\n".format(command))
        #print()

        proc = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
        (out, err) = proc.communicate()
        proc.wait()
        print("Tibber response:\n{}\n".format(str(out, "utf-8")))

    ################################################################################################################################################################

print("Done!")