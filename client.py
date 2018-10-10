import socket
import os
import subprocess
import json
import time

TCP_IP = '192.168.0.105'
TCP_PORT = int(input('Enter Port: '))
BUFFER_SIZE = 10240
TIMEOUT = 10000000


def execute_code(path):
    start = time.time()
    # code = subprocess.Popen(["python3", path], stdout=subprocess.PIPE)
    try:
        code = subprocess.check_call(["python3", path], stdout=subprocess.PIPE)

        # while code.returncode is None:
        #     # output = code.stdout.readline()
        #     # s.send(output)
        #     code.poll()
        end = time.time()
        return "{:.3f}".format(end - start)

    except subprocess.CalledProcessError:
        return "FAIL"


def receive_file(sock, file_size, file_name, chunk_size, path):
    file = open(os.path.join(path, file_name), "wb")

    while file_size > 0:
        current = chunk_size
        if file_size < chunk_size:
            current = file_size
        print(file_size)
        file_data = sock.recv(current)
        file_size -= len(file_data)
        while not file_data:
            file_data = sock.recv(current)
        file.write(file_data)

    file.close()
    return


def my_send(connection, data):
    data = json.dumps(data)
    print('send', data)
    connection.send(bytes(data, 'UTF-8'))


def my_recv(connection):
    data = connection.recv(BUFFER_SIZE)
    print('recv', data)
    data = json.loads(data.decode('UTF-8'))
    return data


def send_folder(connection, path, type, time_taken=None):
    sizes = []
    # To get sizes of each file
    all_files = os.listdir(path)

    for each in all_files:
        file_info = os.stat(path + each)
        file_size = file_info.st_size
        sizes.append(file_size)

    msg = {
        'type': type,
        'file_size': sizes,
        'chunk_size': BUFFER_SIZE,
        'file_name': all_files,
    }

    if time_taken is not None:
        msg['time_taken'] = time_taken

    my_send(connection, msg)
    print('waiting for acknowledge')
    response = my_recv(connection)

    if response['type'] == 'acknowledge_' + type:
        for each in range(len(all_files)):
            file_name = all_files[each]
            f = open(path + file_name, 'rb')
            file_size = sizes[each]
            chunk_size = BUFFER_SIZE

            while file_size > 0:
                print(file_size)
                current = chunk_size
                if file_size < chunk_size:
                    current = file_size
                msg = f.read(current)
                file_size -= current
                connection.send(msg)
            print('Done:' + file_name)

            response = my_recv(connection)
            if not (response['type'] == 'file_received' and response['file_name'] == file_name):
                print('Failure')
                return -1
            else:
                print('Success')
                return 1
    else:
        print('Didnt got response')


def receive_folder(connection, path, received_json):
    if not os.path.exists(path):
        os.makedirs(path)

    response = {'type': "acknowledge_" + received_json['type']}
    connection.send(json.dumps(response).encode('utf-8'))

    chunk_size = received_json["chunk_size"]
    for i in range(len(received_json["file_name"])):
        receive_file(connection, received_json["file_size"][i], received_json["file_name"][i], chunk_size, path)

        file_response = dict()
        file_response["type"] = "file_received"
        file_response["file_name"] = received_json["file_name"][i]

        connection.send(json.dumps(file_response).encode('utf-8'))
        print("received " + received_json["file_name"][i])
    return


def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((TCP_IP, TCP_PORT))
    print("Connected..")

    while True:
        print("Waiting for server..")
        received = s.recv(BUFFER_SIZE)
        print(received)
        received = received.decode('utf-8')
        data = json.loads(received)

        if data["type"] == "question":
            if data["question"] == "role":
                response = dict()
                response['type'] = "introduction"
                response["host"] = socket.gethostname()
                response["role"] = "client"

                s.send(json.dumps(response).encode('utf-8'))

            elif data["question"] == "input_data":
                print("Do you want to continue(y/n): ", end="")
                choice = 'y'
                start_time = time.time()
                while time.time() <= start_time + 5:
                    choice = input()

                response = {'type': "response_input"}
                if choice == 'n':
                    response['response'] = 'no'
                    s.send(json.dumps(response).encode('utf-8'))
                    print("Closing Connection.....")
                    s.close()
                    exit()
                else:
                    response['response'] = 'yes'
                    s.send(json.dumps(response).encode('utf-8'))

        elif data["type"] == "assess":
            cwd = os.getcwd()
            path = os.path.join(cwd, data['type'])
            receive_folder(s, path, data)

        elif data["type"] == "actual_code":
            cwd = os.getcwd()
            path = os.path.join(cwd, 'actual')
            receive_folder(s, path, data)

        elif data["type"] == "actual_input":
            cwd = os.getcwd()
            path = os.path.join(cwd, 'actual')

            receive_folder(s, path, data)

            code_file_path = os.path.join(path, 'code.py')
            output_path_join = os.path.join(path, 'output')
            time_taken = execute_code(code_file_path)

            if time_taken == "FAIL":
                response = {'type': 'finished', 'status': 'failure'}
                s.send(json.dumps(response).encode('utf-8'))

            else:
                response = {'type': 'finished', 'status': 'success'}
                s.send(json.dumps(response).encode('utf-8'))

            print("Waiting for server..")
            received = s.recv(BUFFER_SIZE)
            print(received)
            received = received.decode('utf-8')
            data = json.loads(received)

            if data["type"] == "acknowledge_finished" and time_taken!="FAIL":
                send_folder(s, output_path_join, "result", time_taken)

        elif data["type"] == "error":
            print("Error" + data['error'])


main()
