''' COSC364 Assignment 1
Written by Rean Zhou  and Xingzhuo LI
27-04-2018 '''
import socket
import select
import sys
import time
import random
IP = "127.0.0.1"
own_id = -1
output_ports = {}
input_ports = []
delete_id = []

def print_table(table):
    ''' Prints the routing table in a readable format
        @param table: dictionary representing the routing table '''
    routerids = sorted(table.keys())
    print("Own Router ID: {0}".format(own_id))
    print(" ID ||firsthop|metric|grab flag|drop timeout|grab timeout|")
    print("____________________________________________________________")
    for i in range(0, len(table)):
        info = table[routerids[i]]
        print(" {:>2} ||".format(routerids[i]), end='')
        print(" {:>3} | {:>2} | {:<7} | {:<8} | {:<8} |"\
              .format(info[0], info[1], info[2], str(info[3][0])[:8], str(info[3][1])[:11]))
    print("_____________________________________________________________")

def routing_table(filenm):
    ''' Reads the config from the config file and builds the routing table
        from it. 
        @param filename: name of the config file to read '''
    global own_id
    lines = []
    table = {}
    try:
        c1=open(filenm, 'r')
    except FileFoundError:
        print("Please enter a valid configuration file name")
        return
    
    for i in c1.readlines():
        i=i.split(', ')
        lines.append(i)
    try:    
        own_id = int(lines[0][1])
        if(int(lines[0][1]) > 64000 or int(lines[0][1]) < 1):
            raise ValueError        
        for i in range(1, len(lines[1])):
            input_ports.append(int(lines[1][i]))

        for i in range(1,len(lines[2])):
            temp = lines[2][i]
            temp = temp.split('-')
            router_id = int(temp[-1])
            if(router_id > 64000 or router_id < 1):
                raise ValueError
            portno = int(temp[0])
            output_ports[portno] = router_id
            first_router = router_id
            metric = int(temp[-2])
            flag = False
            timers = [0, 0]
            table[router_id] = [first_router, metric, flag, timers] 
    except ValueError:
        print("Invalid configuration port number")
        return 
    return table

def receiver(table, timeout):
    ''' Checks the sockets to see if any messages have been received.
        @param rt_table: dictionary representing the routing table
    '''
    socket_list=[]
    for i in range(0, len(input_ports)):# create UDP socket and bind these sockets
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((IP, int(input_ports[i]) ))        
        socket_list.append(sock)
    a,b,c = select.select(socket_list,[],[], timeout)
    if a != []:
        s = a[0]
        
        data,addr = s.recvfrom(1024)
        print("----- Received message: " + str(data))
        data = data.decode('utf-8')
        data = data.split(',')
        route_id = int(data[2])
        start = 3 #for normal router table
        start2 = 3 # for reconnect router table whose 
        #garbage_collection_timeout < 20
        start3 = 3 # for reconcet router table which was deleted
        if route_id in delete_id:
            delete_id.remove(route_id)
            while start3 < len(data):
                router_id = int(data[start3])
                if router_id == own_id:
                    metric = int(data[start3+1])
                    table[route_id] = [route_id,metric,False,[0,0]]
                start3 = start3 + 2            
        
        if table[route_id][1] == 16 and table[route_id][3][1] < 20:
            while start2 < len(data):
                router_id = int(data[start2])
                if router_id == own_id:
                    metric = int(data[start2+1])
                    table[route_id] = [route_id,metric,False,[0,0]]
                start2 = start2 + 2
        try:
            if(table[route_id][1] != 16):
                table[route_id][-1][0] = 0 
                table[route_id][-1][1] = 0
                table[route_id][2] = False    
            else:
                table[route_id][2] = True    
        except:         
            print("Fail to reset the timer")
        print("start",start)
        print("data",len(data))
        while start < len(data):
            print("hello")
            try:
                rec_id = int(data[start]) 
                router_id = int(data[start])
                metric = min(int(data[start+1]) + table[route_id][1], 16)
                print(metric)
            except:
                break
            
            if metric not in range(0,17):
                print("Packet does not conform. Metric not in range 0-16")
                break
            if router_id not in output_ports.values() and router_id != own_id and metric != 16:
                if rec_id not in table.keys():
                    table[router_id] = [route_id, metric, False, [0,0]]

                if (metric < table[router_id][1]):
                    table[router_id][1] = metric 
                    table[router_id][0] = route_id
                
                if (route_id == table[router_id][0]) and table[router_id][1] !=16:
                    table[router_id][1] = metric 
                    table[router_id][0] = route_id
                    table[router_id][-1][0] = 0 
                    table[router_id][-1][1] = 0
                    table[router_id][2] = False

            start += 2
            print_table(table)
    return table

def send_message(table):
    ''' Sends an update message to all direct neighbours
        @param table: dictionary representing the routing table '''
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for port in output_ports:  
        command = "2"
        version = "2" 
        msg = command + ',' + version + ','+ str(own_id)
       
        for i in table.keys():
            value = table[i]
            msg += ',' + str(i) + ','
            metric = str(value[1]) if i not in table.values() else 16
            msg += metric        
        msg = msg.encode('utf-8')
        sock.sendto(msg, (IP, port))

def update_timers(table, time):
    ''' Adds time onto all routing table entry timers.
        @param table: dictionary representing the routing table
        @param time: time to add to the timers. '''
    route_invalid_timeout = 30
    garbage_collection_timeout = 20
    for key in sorted(table.keys()):
        if table[key][2] == False:
            table[key][-1][0] += time
            if table[key][-1][0] > route_invalid_timeout:
                table[key][1] = 16 
                table[key][2] = True
                routers = []
                for router in sorted(table.keys()):
                    if table[router][0] == key:
                        routers.append(router)    
                for router in routers:
                    table[router][1] = 16            
        else:
            table[key][-1][1] += time
            if table[key][-1][1] > garbage_collection_timeout:
                if key not in delete_id:
                    delete_id.append(key)
                del table[key]
    print("\n")

def main(argv):
    counter = 0
    rt_table = routing_table(sys.argv[1])
    if len(argv) != 1:
        print("Please enter configuration file name as the parameter")
        return
    else:    
        while 1:
            print("loop " + str(counter))
            starttime = time.time()
            randomtime = random.randint(0,2)
            timeout = randomtime
            last = starttime - time.time()
            time.sleep(1)
            rt_table = receiver(rt_table, timeout) 
            timer_incr = time.time() - starttime
            update_timers(rt_table,timer_incr)
            timeout = randomtime - last
            print("loop{}: result".format(counter))
            print_table(rt_table)
            print("\n")
            send_message(rt_table)
            counter += 1

if __name__ == "__main__":
    main(sys.argv[1:])
