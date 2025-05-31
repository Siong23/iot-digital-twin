#!/usr/bin/env python3
"""
IoT Device Credentials Dictionary
Educational Purpose Only - For Controlled Lab Environment

This file contains a comprehensive list of default credentials commonly found on IoT devices.
These credentials are used for security research and penetration testing in controlled environments.
"""

# Comprehensive IoT Device Credentials Database
# Format: (username, password, device_description)
IOT_CREDENTIALS = [
    # Lab/Target Specific Credentials (High Priority)
    ("ipcamadmin", "admin"),      # Digital IPCam credentials
    ("temphumidadmin", "admin"),  # Digital TempHumidSensor credentials
    ("temphumid", "digital"),
    ("sensor", "temphumid"),
    
    # Generic/Common Credentials
    ("admin", "admin"),
    ("admin", "password"),
    ("admin", "123456"),
    ("admin", ""),
    ("root", "root"),
    ("root", "admin"),
    ("root", "password"),
    ("root", "123456"),
    ("root", ""),
    ("user", "user"),
    ("user", "password"),
    ("guest", "guest"),
    ("guest", ""),
    ("default", "default"),
    ("support", "support"),
    
    # Router Specific Credentials
    ("admin", "admin123"),
    ("admin", "1234"),
    ("admin", "12345"),
    ("admin", "router"),
    ("admin", "changeme"),
    ("administrator", "administrator"),
    ("administrator", "admin"),
    ("cisco", "cisco"),
    ("linksys", "linksys"),
    ("netgear", "netgear"),
    ("dlink", "dlink"),
    ("asus", "asus"),
    ("tp-link", "admin"),
    ("tplink", "admin"),
    
    # Cisco Devices
    ("cisco", "cisco"),
    ("admin", "cisco"),
    ("enable", "cisco"),
    ("manager", "manager"),
    ("root", "cisco"),
    ("service", "service"),
    
    # Netgear
    ("admin", "password"),
    ("admin", "netgear1"),
    ("admin", "1234"),
    ("netgear", "password"),
    
    # D-Link
    ("admin", ""),
    ("admin", "admin"),
    ("user", ""),
    ("dlink", "dlink"),
    
    # ASUS
    ("admin", "admin"),
    ("admin", "password"),
    ("asus", "asus"),
    
    # TP-Link
    ("admin", "admin"),
    ("admin", "1234"),
    ("admin", "21232f297a57a5a743894a0e4a801fc3"),
    
    # Belkin
    ("", ""),
    ("admin", ""),
    ("belkin", "belkin"),
    
    # Linksys
    ("admin", "admin"),
    ("linksys", "admin"),
    ("admin", ""),
    
    # Buffalo
    ("root", ""),
    ("admin", "password"),
    ("buffalo", "buffalo"),
    
    # IP Camera Credentials
    ("admin", "admin"),
    ("admin", "12345"),
    ("admin", "123456"),
    ("admin", "888888"),
    ("admin", "666666"),
    ("admin", "54321"),
    ("admin", "pass"),
    ("admin", "camera"),
    ("admin", "security"),
    ("root", "pass"),
    ("root", "camera"),
    ("root", "vizxv"),
    ("root", "ikwb"),
    ("root", "dreambox"),
    ("user", "user"),
    ("viewer", "viewer"),
    ("guest", "12345"),
    ("camera", "camera"),
    ("ubnt", "ubnt"),
    ("service", "service"),
    ("supervisor", "supervisor"),
    ("tech", "tech"),
    ("operator", "operator"),
    
    # DVR/NVR Credentials
    ("admin", "admin"),
    ("admin", "12345"),
    ("admin", "123456"),
    ("admin", "password"),
    ("admin", ""),
    ("root", "root"),
    ("root", "admin"),
    ("root", "12345"),
    ("888888", "888888"),
    ("666666", "666666"),
    ("abc123", "abc123"),
    ("admin", "abc123"),
    ("admin", "1111"),
    ("admin", "1111111"),
    ("admin", "54321"),
    ("admin", "7ujMko0admin"),
    ("admin", "pass"),
    ("admin", "meinsm"),
    ("default", "default"),
    ("dvr", "dvr"),
    ("guest", "guest"),
    ("demo", "demo"),
    
    # IoT Devices & Smart Home
    ("admin", "admin"),
    ("admin", "password"),
    ("admin", "smarthome"),
    ("admin", "iot"),
    ("pi", "raspberry"),
    ("pi", "admin"),
    ("ubuntu", "ubuntu"),
    ("debian", "debian"),
    ("iot", "iot"),
    ("device", "device"),
    ("smart", "smart"),
    ("home", "home"),
    ("sensor", "sensor"),
    ("gateway", "gateway"),
    ("hub", "hub"),
    
    # Smart TV Credentials
    ("admin", "admin"),
    ("admin", "1234"),
    ("admin", "0000"),
    ("root", "samsung"),
    ("root", "lg"),
    ("root", "sony"),
    ("samsung", "samsung"),
    ("lg", "lg"),
    ("sony", "sony"),
    ("smart", "smart"),
    
    # Printer Credentials
    ("admin", "admin"),
    ("admin", "hp"),
    ("admin", "canon"),
    ("admin", "epson"),
    ("admin", "brother"),
    ("admin", "lexmark"),
    ("admin", "xerox"),
    ("admin", "ricoh"),
    ("admin", "kyocera"),
    ("root", "admin"),
    ("service", "service"),
    ("tech", "tech"),
    
    # NAS Devices
    ("admin", "admin"),
    ("admin", "password"),
    ("admin", "nas"),
    ("admin", "storage"),
    ("root", "admin"),
    ("nas", "nas"),
    ("qnap", "qnap"),
    ("synology", "synology"),
    ("drobo", "drobo"),
    ("netgear", "netgear"),
    
    # Smart Home Hubs
    ("admin", "admin"),
    ("admin", "smartthings"),
    ("admin", "wink"),
    ("admin", "vera"),
    ("admin", "hubitat"),
    ("admin", "homey"),
    ("root", "toor"),
    ("smarthub", "smarthub"),
    
    # Industrial IoT
    ("admin", "admin"),
    ("admin", "industrial"),
    ("admin", "scada"),
    ("admin", "plc"),
    ("operator", "operator"),
    ("engineer", "engineer"),
    ("maintenance", "maintenance"),
    ("service", "service"),
    ("technician", "technician"),
    ("supervisor", "supervisor"),
    ("manager", "manager"),
    
    # Medical Devices
    ("admin", "admin"),
    ("admin", "medical"),
    ("admin", "hospital"),
    ("admin", "patient"),
    ("service", "service"),
    ("tech", "tech"),
    ("biomedical", "biomedical"),
    
    # Raspberry Pi & Embedded
    ("pi", "raspberry"),
    ("pi", "pi"),
    ("pi", "admin"),
    ("root", "raspberry"),
    ("ubuntu", "ubuntu"),
    ("debian", "debian"),
    ("alarm", "alarm"),
    ("osmc", "osmc"),
    ("openelec", "openelec"),
    ("kodi", "kodi"),
    ("xbmc", "xbmc"),
    ("volumio", "volumio"),
    ("dietpi", "dietpi"),
    
    # Security Systems
    ("admin", "admin"),
    ("admin", "security"),
    ("admin", "alarm"),
    ("admin", "1234"),
    ("admin", "0000"),
    ("installer", "installer"),
    ("master", "master"),
    ("user", "1234"),
    ("alarm", "alarm"),
    ("security", "security"),
    
    # Weather Stations
    ("admin", "admin"),
    ("admin", "weather"),
    ("admin", "station"),
    ("weather", "weather"),
    ("station", "station"),
    ("davis", "davis"),    ("oregon", "oregon"),
    
    # Custom/Lab Specific (Additional)
    ("monitor", "temperature"),
    ("humidity", "sensor"),
    ("environment", "monitor"),
    ("climate", "control"),
    ("thermo", "stat"),
    
    # Additional common patterns
    ("test", "test"),
    ("demo", "demo"),
    ("sample", "sample"),
    ("example", "example"),
    ("temp", "temp"),
    ("monitor", "monitor"),
    ("sensor1", "sensor1"),
    ("device1", "device1"),
    ("node1", "node1"),
    ("gateway1", "gateway1"),
]

def get_credentials():
    """
    Returns the list of credentials as tuples (username, password)
    """
    return IOT_CREDENTIALS

def get_credentials_count():
    """
    Returns the total number of credential pairs
    """
    return len(IOT_CREDENTIALS)

def get_device_specific_credentials(device_type):
    """
    Returns credentials filtered by device type keywords
    
    Args:
        device_type (str): Type of device (router, camera, dvr, iot, etc.)
    
    Returns:
        list: List of (username, password) tuples relevant to device type
    """
    device_keywords = {
        'router': ['cisco', 'netgear', 'dlink', 'asus', 'linksys', 'tplink', 'belkin', 'buffalo'],
        'camera': ['admin', 'root', 'user', 'viewer', 'camera', 'ubnt', 'service'],
        'dvr': ['admin', 'root', '888888', '666666', 'abc123', 'default', 'dvr'],
        'iot': ['pi', 'ubuntu', 'debian', 'iot', 'device', 'smart', 'sensor', 'temphumid'],
        'printer': ['admin', 'service', 'tech'],
        'nas': ['admin', 'nas', 'qnap', 'synology', 'drobo'],
    }
    
    if device_type.lower() not in device_keywords:
        return IOT_CREDENTIALS
    
    # Filter credentials based on device type
    filtered = []
    keywords = device_keywords[device_type.lower()]
    
    for username, password in IOT_CREDENTIALS:
        # Include if username or password contains device-specific keywords
        if any(keyword in username.lower() or keyword in password.lower() for keyword in keywords):
            filtered.append((username, password))
    
    # Always include common generic credentials
    generic_creds = [
        ("admin", "admin"), ("admin", "password"), ("admin", "123456"),
        ("root", "root"), ("root", "admin"), ("user", "user")
    ]
    
    for cred in generic_creds:
        if cred not in filtered:
            filtered.append(cred)
    
    return filtered

if __name__ == "__main__":
    # Test the credentials module
    print(f"Total credentials: {get_credentials_count()}")
    print(f"First 10 credentials: {get_credentials()[:10]}")
    print(f"IoT specific credentials: {len(get_device_specific_credentials('iot'))}")
