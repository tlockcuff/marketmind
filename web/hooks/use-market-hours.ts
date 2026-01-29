"use client";

import { useState, useEffect, useRef } from "react";

interface MarketHoursProps {
  isOpen: boolean;
  timeUntilOpen: number | null;
  timeUntilClose: number | null;
}

export function useMarketHours({ isOpen, timeUntilOpen, timeUntilClose }: MarketHoursProps) {
  const [displayText, setDisplayText] = useState<string>("—");
  const countdownRef = useRef<number | null>(null);

  useEffect(() => {
    // Reset countdown when props change
    if (isOpen && timeUntilClose !== null) {
      countdownRef.current = timeUntilClose;
    } else if (!isOpen && timeUntilOpen !== null) {
      countdownRef.current = timeUntilOpen;
    } else {
      countdownRef.current = null;
    }

    const updateDisplay = () => {
      const seconds = countdownRef.current;
      
      if (seconds === null || seconds < 0) {
        setDisplayText("—");
        return;
      }

      if (isOpen) {
        // Market is open - show time until close
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        
        if (hours > 0) {
          setDisplayText(`Closes in ${hours}h ${minutes}m`);
        } else if (minutes > 0) {
          setDisplayText(`Closes in ${minutes}m ${secs}s`);
        } else {
          setDisplayText(`Closes in ${secs}s`);
        }
      } else {
        // Market is closed - show time until open
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        
        if (hours > 0) {
          setDisplayText(`Opens in ${hours}h ${minutes}m`);
        } else if (minutes > 0) {
          setDisplayText(`Opens in ${minutes}m ${secs}s`);
        } else {
          setDisplayText(`Opens in ${secs}s`);
        }
      }
    };

    updateDisplay();

    // Update every second for smooth countdown
    const interval = setInterval(() => {
      if (countdownRef.current !== null && countdownRef.current > 0) {
        countdownRef.current -= 1;
        updateDisplay();
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [isOpen, timeUntilOpen, timeUntilClose]);

  return displayText;
}
