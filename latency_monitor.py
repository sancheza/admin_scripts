#!/usr/bin/env python3
import subprocess
import time
import statistics
import platform
import smtplib
from email.message import EmailMessage
from datetime import datetime
import os
import argparse
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_PASS")
EMAIL_TO = os.getenv("SYSTEM_ADMIN")  # Ensure this is set in your .env file

LOG_FILE = "latency_monitor.log"
DEFAULT_TARGET = "8.8.8.8"
PING_COUNT = 100
DEFAULT_SLEEP_INTERVAL = 3600  # 1 hour

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Network Latency Monitor: Continuously monitors network latency to a target IP/host and "
                    "logs statistics. Sends email alerts when packet loss is detected.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "-t", "--target",
        default=DEFAULT_TARGET,
        help="Target IP address or hostname to ping"
    )
    
    parser.add_argument(
        "-i", "--interval",
        type=int,
        default=DEFAULT_SLEEP_INTERVAL,
        help="Sleep interval between ping tests in seconds"
    )
    
    parser.add_argument(
        "-c", "--count",
        type=int,
        default=PING_COUNT,
        help="Number of ICMP packets to send per test"
    )
    
    parser.add_argument(
        "-l", "--log",
        default=LOG_FILE,
        help="Path to the log file"
    )
    
    return parser.parse_args()

def run_ping(target):
    system = platform.system()
    count_flag = "-n" if system == "Windows" else "-c"
    try:
        result = subprocess.run(
            ["ping", count_flag, str(PING_COUNT), target],
            capture_output=True,
            text=True
        )
        return result.stdout
    except Exception as e:
        return f"Ping command failed: {e}"

def parse_ping_output(output):
    latencies = []
    packet_loss = None
    system = platform.system()

    for line in output.splitlines():
        line = line.strip()

        # Latency lines
        if "time=" in line.lower():
            try:
                time_part = [part for part in line.split() if "time=" in part.lower() or "time<" in part.lower()]
                if time_part:
                    latency_str = time_part[0].split("=")[-1].replace("ms", "").replace("<", "").strip()
                    latencies.append(float(latency_str))
            except Exception:
                continue

        # Packet loss for Unix/Linux/macOS
        if system != "Windows" and "packet loss" in line:
            try:
                packet_loss = float(line.split("%")[0].split()[-1])
            except Exception:
                pass

        # Packet loss for Windows
        if system == "Windows" and "lost =" in line.lower():
            try:
                loss_part = line.lower().split("lost =")[1]
                lost = int(loss_part.split(",")[0].strip())
                sent_part = line.lower().split("sent =")[1]
                sent = int(sent_part.split(",")[0].strip())
                packet_loss = (lost / sent) * 100
            except Exception:
                pass

    stats = {
        "mean": round(statistics.mean(latencies), 2) if latencies else None,
        "median": round(statistics.median(latencies), 2) if latencies else None,
        "min": round(min(latencies), 2) if latencies else None,
        "max": round(max(latencies), 2) if latencies else None,
        "packet_loss": round(packet_loss, 2) if packet_loss is not None else 100.0
    }

    return stats

def send_email(subject, body):
    if not GMAIL_USER or not GMAIL_PASS:
        print("GMAIL_USER or GMAIL_PASS not set. Skipping email.")
        return

    msg = EmailMessage()
    msg["From"] = GMAIL_USER
    msg["To"] = EMAIL_TO
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_PASS)
            smtp.send_message(msg)
            print("Email sent.")
    except Exception as e:
        print(f"Failed to send email: {e}")

def log_results(stats, log_file):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = (f"[{timestamp}] Packet Loss: {stats['packet_loss']}% | "
            f"Mean: {stats['mean']} ms | Median: {stats['median']} ms | "
            f"Min: {stats['min']} ms | Max: {stats['max']} ms\n")

    with open(log_file, "a") as f:
        f.write(line)

    print(line.strip())

    # Email alert for any packet loss
    if stats["packet_loss"] > 0:
        send_email(
            subject=f"Ping Alert: Packet Loss Detected ({stats['packet_loss']}%)",
            body=line
        )

def main():
    args = parse_arguments()
    
    print(f"Latency Monitor Started")
    print(f"Target: {args.target}")
    print(f"Interval: {args.interval} seconds")
    print(f"Ping count: {args.count}")
    print(f"Log file: {args.log}")
    
    global PING_COUNT
    PING_COUNT = args.count
    
    while True:
        output = run_ping(args.target)
        stats = parse_ping_output(output)
        log_results(stats, args.log)
        time.sleep(args.interval)

if __name__ == "__main__":
    main()
