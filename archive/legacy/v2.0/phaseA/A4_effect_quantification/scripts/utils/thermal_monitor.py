#!/usr/bin/env python3
"""
Thermal monitoring utility for CPU-intensive operations.

Monitors CPU temperatures and reports when approaching thermal limits.

Usage:
    # Monitor for 5 minutes with 85°C limit
    python utils/thermal_monitor.py --temp_limit 85 --duration 300
"""

import psutil
import time
import argparse
from datetime import datetime
from pathlib import Path


def get_cpu_temperatures():
    """
    Get CPU temperatures using psutil.

    Returns:
        dict: CPU temperature readings
    """
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return None

        # Try common CPU temp sensor names
        for sensor_name in ['coretemp', 'k10temp', 'zenpower', 'cpu_thermal']:
            if sensor_name in temps:
                return temps[sensor_name]

        # Fallback: return first available sensor
        if temps:
            return list(temps.values())[0]

        return None

    except AttributeError:
        # psutil.sensors_temperatures not available on this system
        return None


def get_max_cpu_temp(temps):
    """
    Extract maximum CPU temperature from sensor readings.

    Args:
        temps: List of temperature sensor objects

    Returns:
        float: Maximum temperature, or None if unavailable
    """
    if temps is None:
        return None

    try:
        max_temp = max([t.current for t in temps if hasattr(t, 'current')])
        return max_temp
    except (ValueError, TypeError):
        return None


def get_cpu_usage():
    """
    Get current CPU usage percentage.

    Returns:
        float: CPU usage percentage (0-100)
    """
    return psutil.cpu_percent(interval=1)


def monitor_thermal(temp_limit: float = 85.0, duration: int = 300, interval: int = 30):
    """
    Monitor CPU temperatures for a specified duration.

    Args:
        temp_limit: Temperature limit in Celsius
        duration: Monitoring duration in seconds
        interval: Reporting interval in seconds
    """
    print("=" * 80)
    print("THERMAL MONITORING")
    print("=" * 80)
    print(f"Temperature limit: {temp_limit}°C")
    print(f"Duration: {duration}s ({duration/60:.1f} minutes)")
    print(f"Reporting interval: {interval}s")
    print("")

    start_time = time.time()
    max_temp_seen = 0
    readings = []

    while (time.time() - start_time) < duration:
        temps = get_cpu_temperatures()
        max_temp = get_max_cpu_temp(temps)
        cpu_usage = get_cpu_usage()

        timestamp = datetime.now().strftime("%H:%M:%S")

        if max_temp is not None:
            max_temp_seen = max(max_temp_seen, max_temp)
            readings.append(max_temp)

            status = "✅"
            if max_temp >= temp_limit:
                status = "🚨 THERMAL LIMIT"
            elif max_temp >= temp_limit - 5:
                status = "⚠️  WARNING"

            print(f"[{timestamp}] CPU: {cpu_usage:5.1f}% | Temp: {max_temp:5.1f}°C | {status}")

        else:
            print(f"[{timestamp}] CPU: {cpu_usage:5.1f}% | Temp: N/A (sensors not available)")

        time.sleep(interval)

    elapsed = time.time() - start_time

    print("")
    print("=" * 80)
    print("MONITORING COMPLETE")
    print("=" * 80)
    print(f"Duration: {elapsed:.0f}s ({elapsed/60:.1f} minutes)")

    if readings:
        avg_temp = sum(readings) / len(readings)
        print(f"Max temperature: {max_temp_seen:.1f}°C")
        print(f"Avg temperature: {avg_temp:.1f}°C")
        print(f"Temp limit: {temp_limit}°C")

        if max_temp_seen >= temp_limit:
            print("")
            print("🚨 THERMAL LIMIT EXCEEDED - reduce core count or improve cooling")
            return 1
        elif max_temp_seen >= temp_limit - 5:
            print("")
            print("⚠️  Temperature close to limit - monitor carefully during full run")
            return 0
        else:
            print("")
            print("✅ Thermal performance OK")
            return 0
    else:
        print("⚠️  Temperature sensors not available - cannot monitor thermals")
        return 0


def main():
    parser = argparse.ArgumentParser(description='Monitor CPU temperatures')
    parser.add_argument('--temp_limit', type=float, default=85.0,
                       help='Temperature limit in Celsius')
    parser.add_argument('--duration', type=int, default=300,
                       help='Monitoring duration in seconds')
    parser.add_argument('--interval', type=int, default=30,
                       help='Reporting interval in seconds')

    args = parser.parse_args()

    return monitor_thermal(args.temp_limit, args.duration, args.interval)


if __name__ == "__main__":
    import sys
    sys.exit(main())
