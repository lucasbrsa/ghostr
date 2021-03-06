import sys
from socket import *
from threading import Thread
from constants import IP, BUFF_SIZE, FORMAT
from protocol import message_type, parse_message, remove_first_word, unpack_message

if len(sys.argv) != 2:
    print("error: usage: python client.py <SERVER_PORT>")
    sys.exit()

PORT = int(sys.argv[1])
ADDR = (IP, PORT)

client = socket(AF_INET, SOCK_STREAM)
client.connect(ADDR)


class P2P:
    def __init__(self, dest_addr):
        self.dest_addr = dest_addr
        self.priv_port = None
        self.alive = True

    def make_server_socket(self):
        server = socket(AF_INET, SOCK_STREAM)
        server.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        server.bind((IP, 0))
        server.listen()
        self.priv_port = server.getsockname()[1]
        return server

    def peer_conn_handler(self, client):
        msg = ""
        while self.alive:
            msg = client.recv(BUFF_SIZE).decode(FORMAT)
            print(msg)

    def recv_handler(self):
        server = self.make_server_socket()
        while True:
            client, addr = server.accept()
            t = Thread(target=self.peer_conn_handler, args=[client])
            t.start()


class ClientCore(Thread):
    def __init__(self):
        Thread.__init__(self)

    def run(self):
        while True:
            try:
                msg = client.recv(BUFF_SIZE).decode(FORMAT)
                if msg == 0 or msg == "":
                    print("CLIENT THREAD() IS BEING SHUTDOWN from bad response")
                    sys.exit()
                # --------------------------------------------------------- /MSG
                if message_type(msg) == "MSG":
                    print(parse_message(msg)["FROM"] + ": " + parse_message(msg)["BODY"])
                # --------------------------------------------------------- /STARTPRIVATE
                elif message_type(msg) == "PRIVREQ":
                    dest_sock = parse_message(msg)["DEST"]
                    print("addr: " + dest_sock)
                # --------------------------------------------------------- /WHOELSE
                elif message_type(msg) == "WHOELSE" or message_type(msg) == "WHOELSESINCE":
                    print(parse_message(msg)["BODY"])
                # --------------------------------------------------------- /LOGGEDIN
                elif message_type(msg) == "LOGGEDIN":
                    print(parse_message(msg)["WHO"] + " logged in")
                # --------------------------------------------------------- /BLOCK
                elif message_type(msg) == "BLOCK":
                    if not int(parse_message(msg)["RET"]):
                        print(parse_message(msg)["ERR"])
                    else:
                        print(parse_message(msg)["WHO"] + " was blocked")
                # --------------------------------------------------------- /UNBLOCK
                elif message_type(msg) == "UNBLOCK":
                    if not int(parse_message(msg)["RET"]):
                        print(parse_message(msg)["ERR"])
                    else:
                        print(parse_message(msg)["WHO"] + " was unblocked")
                # --------------------------------------------------------- /LOGOUT
                elif message_type(msg) == "LOGOUT":
                    break
                elif message_type(msg) == "LOGGEDOUT":
                    print(parse_message(msg)["WHO"] + " logged out")
                else:
                    # undefined server behaviour
                    pass
            except Exception:
                pass

        # exit the thread
        sys.exit()


def user_auth():
    # -------------------------------------------------- /AUTH
    username = input("Username: ")
    msg = f"""TYPE: LOGON;;WHO: {username};;"""

    # server logon response
    client.send(msg.encode(FORMAT))
    msg = client.recv(BUFF_SIZE).decode(FORMAT)

    # auth flags
    authorised_logon = int(parse_message(msg)["RET"])
    new_user = int(parse_message(msg)["NEW"])
    err_code = parse_message(msg)["ERR"]

    if not authorised_logon and err_code != "0":
        print(err_code)
        return False
    # --------------------------------- /NEW USERS
    elif new_user:
        password = input("This is a new user. Enter a password: ")
        msg = f"TYPE: AUTH;;WHO: {username};;PASW: {password};;NEW: 1;;"
        client.send(msg.encode(FORMAT))
    else:
        # ----------------------------- /EXISTING USERS
        # initial password prompt
        password = input("Password: ")
        msg = f"TYPE: AUTH;;WHO: {username};;PASW: {password};;NEW: 0;;"
        client.send(msg.encode(FORMAT))

        msg = client.recv(BUFF_SIZE).decode(FORMAT)
        correct_pasw = int(parse_message(msg)["PASW"])
        attempts_left = int(parse_message(msg)["ATMP"])

        # keep prompting until correct
        while not correct_pasw:
            if attempts_left == 0:
                print("Invalid Password. Your account has been blocked. Please try again later")
                return False

            print("Invalid Password. Please try again")
            password = input("Password: ")
            msg = f"TYPE: AUTH;;WHO: {username};;PASW: {password};;NEW: 0;;"
            client.send(msg.encode(FORMAT))

            msg = client.recv(BUFF_SIZE).decode(FORMAT)
            correct_pasw = int(parse_message(msg)["PASW"])
            attempts_left = int(parse_message(msg)["ATMP"])

    print(f"[CONNECTED] Client connected to server")
    return username


def send_msg(username):
    connected = True
    while connected:
        user_input = input()
        if user_input == "logout":
            msg = f"TYPE: LOGOUT;;WHO: {username};;"
            connected = False
        elif "broadcast" in user_input:
            msg = f"TYPE: BROADCAST;;FROM: {username};;BODY: {remove_first_word(user_input)};;"
        elif "message" in user_input:
            recipient, body = unpack_message(user_input)
            msg = f"TYPE: MSG;;FROM: {username};;TO: {recipient};;BODY: {body};;"
        elif user_input == "whoelse":
            msg = f"TYPE: WHOELSE;;FROM: {username};;"
        elif "whoelsesince" in user_input:
            msg = f"TYPE: WHOELSESINCE;;WHEN: {remove_first_word(user_input)};;FROM: {username};;"
        elif "startprivate" in user_input:
            msg = f"TYPE: PRIVREQ;;TO: {remove_first_word(user_input)};;FROM: {username};;"
        elif "unblock" in user_input:
            msg = f"TYPE: UNBLOCK;;WHO: {remove_first_word(user_input)};;BLOCKER: {username};;"
        elif "block" in user_input:
            msg = f"TYPE: BLOCK;;WHO: {remove_first_word(user_input)};;BLOCKER: {username};;"
        else:
            print("Error. Invalid command")
            continue  # avoid sending an empty message (restart loop)

        client.send(msg.encode(FORMAT))


def main():

    recv_thread = ClientCore()

    authed_username = user_auth()
    if authed_username:
        recv_thread.start()
        send_msg(authed_username)
        client.close()
        sys.exit()
    else:
        client.close()
        sys.exit()


if __name__ == "__main__":
    main()
