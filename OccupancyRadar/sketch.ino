#include <Arduino.h>
#include <vector>
#include "time.h"

#define RX2_PIN 16
#define TX2_PIN 17

uint32_t rdmap[20][16]; //20 doppler × 16 range gates
bool paused = false;
bool timeSet = false;

static unsigned long lastPrint = 0;

//Runtime selection: when true the reader prints a single-line hex dump
//of available Serial2 bytes, when false it parses framed packets.
bool singleLinePrint = true; //change to switch between print types

/*
  Purpose: Read frames from Serial2 (mmWave sensor) and print data to
  Serial for debugging. The sketch also supports sending a SETTIME
  command from the host (via Serial) and a small helper to send a
  single hex payload to the sensor via Serial2.

  Notes: This file preserves the original runtime behaviour. Only
  comments and small syntax fixes were applied to improve readability
  and maintainability; no algorithmic changes were made.
*/

//Time helpers

//Set the system time from manual components received over Serial.
//This is used when the host sends a `SETTIME` command. Optional milliseconds are supported.
void setManualTime(int year, int month, int day, int hour, int minute, int second, int millis = 0) {
  struct tm tm;
  tm.tm_year = year - 1900;
  tm.tm_mon  = month - 1;
  tm.tm_mday = day;
  tm.tm_hour = hour;
  tm.tm_min  = minute;
  tm.tm_sec  = second;

  time_t t = mktime(&tm);
  struct timeval now = { .tv_sec = t, .tv_usec = millis * 1000 };
  settimeofday(&now, NULL);
}

//Return a readable timestamp (with milliseconds) using RTC + gettimeofday.
String getTimestamp() {
  struct tm timeinfo;
  struct timeval tv;
  if (!getLocalTime(&timeinfo)) {
    return "Time Error";
  }
  gettimeofday(&tv, nullptr);

  char ts[32];
  // Format: YYYY-MM-DD HH:MM:SS.mmm
  snprintf(ts, sizeof(ts), "%04d-%02d-%02d %02d:%02d:%02d.%03ld",
           timeinfo.tm_year + 1900,
           timeinfo.tm_mon + 1,
           timeinfo.tm_mday,
           timeinfo.tm_hour,
           timeinfo.tm_min,
           timeinfo.tm_sec,
           (long)(tv.tv_usec / 1000));
  return String(ts);
}

//Initialize Serial and Serial2 interfaces.
void setup() {
  Serial.begin(115200);

  unsigned long startAttemptTime = millis();
  while (!Serial && millis() - startAttemptTime < 2000) { delay(100); }
  Serial.println("Serial Monitor Initialized.");

  Serial2.begin(115200, SERIAL_8N1, RX2_PIN, TX2_PIN);
  Serial.println("Serial2 Initialized on RX:" + String(RX2_PIN) + ", TX:" + String(TX2_PIN));

  //Send a startup hex payload to the device
  String hex_to_send = "FDFCFBFA0800120000000000000004030201"; //change depending on wanted radar mode
  Serial.println("Sending Hex Data over Serial2...");
  sendHexData(hex_to_send);
  Serial.println("Hex Data Sent.");
}

//main loop: handle commands from Serial and read data from Serial2.
void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    //Handle SETTIME command from host
    if (cmd.startsWith("SETTIME")) {
      // Accept both `SETTIME YYYY-MM-DD HH:MM:SS` and `SETTIME YYYY-MM-DD HH:MM:SS.mmm`
      String payload = cmd.substring(8);
      payload.trim();

      int spaceIdx = payload.indexOf(' ');
      if (spaceIdx > 0) {
        String datePart = payload.substring(0, spaceIdx);
        String timePart = payload.substring(spaceIdx + 1);

        int year   = datePart.substring(0, 4).toInt();
        int month  = datePart.substring(5, 7).toInt();
        int day    = datePart.substring(8, 10).toInt();

        int dotIdx = timePart.indexOf('.');
        String secPart = (dotIdx >= 0) ? timePart.substring(6, dotIdx) : timePart.substring(6);
        String msPart  = (dotIdx >= 0) ? timePart.substring(dotIdx + 1) : String("0");

        int hour   = timePart.substring(0, 2).toInt();
        int minute = timePart.substring(3, 5).toInt();
        int second = secPart.toInt();
        int millis = msPart.toInt();

        setManualTime(year, month, day, hour, minute, second, millis);
        timeSet = true;
        Serial.println("Time updated from laptop!");
        Serial.print("Time updated to: ");
        Serial.println(getTimestamp());
      }
    }

    //Handle pause and resume commands
    if (cmd == "s" || cmd == "stop") {
      paused = true;
      Serial.println("Program paused. Send 'r' or 'resume' to continue.");
    } else if (cmd == "r" || cmd == "resume") {
      paused = false;
      Serial.println("Resuming program.");
    }

    //Mode selection: `mode raw` prints a single-line hex dump of the
    //Serial2 buffer; `mode framed` resumes framed packet parsing.
    if (cmd.equalsIgnoreCase("mode raw")) {
      singleLinePrint = true;
      Serial.println("Read mode: raw single-line hex dump");
    } else if (cmd.equalsIgnoreCase("mode framed") || cmd.equalsIgnoreCase("mode frame")) {
      singleLinePrint = false;
      Serial.println("Read mode: framed packet parsing");
    }
  }

  if (paused) {
    delay(50);
    return;
  }

  /*
  if (!timeSet) {
    // Skip parsing until RTC is valid
    delay(100);
    return;
  }
  */


  //Read from Serial2 using the selected reader method.
  readSerialData();
  //delay(1000);
}

//Send hex data
//Convert a hex string into bytes and write them to Serial2.
void sendHexData(String hexString) {
  int hexStringLength = hexString.length();
  if (hexStringLength % 2 != 0) {
    Serial.println("Error: Hex string must have an even number of characters.");
    return;
  }
  int byteCount = hexStringLength / 2;
  byte hexBytes[byteCount];
  for (int i = 0; i < hexStringLength; i += 2) {
    String byteString = hexString.substring(i, i + 2);
    byte hexByte = (byte)strtoul(byteString.c_str(), NULL, 16);
    hexBytes[i / 2] = hexByte;
  }
  Serial.print("Sending "); Serial.print(byteCount); Serial.println(" bytes");
  Serial2.write(hexBytes, byteCount);
}

//Frame parsing
void readSerialData() {
  if (singleLinePrint) {
    //Single-line mode: wait for a full framed packet, then print all 320 values in one line
    static bool inFrame = false;
    static std::vector<uint8_t> frameBuf;

    while (Serial2.available() > 0) {
      byte b = Serial2.read();

      //Detect header start (0xAA … depending on your radar mode)
      if (!inFrame && b == 0xAA) {
        frameBuf.clear();
        frameBuf.push_back(b);
        inFrame = true;
        continue;
      }

      if (inFrame) {
        frameBuf.push_back(b);
        //Detect trailer (FD FC FB FA)
        int n = frameBuf.size();
        if (n >= 4 &&
            frameBuf[n - 4] == 0xFD &&
            frameBuf[n - 3] == 0xFC &&
            frameBuf[n - 2] == 0xFB &&
            frameBuf[n - 1] == 0xFA) {
          int payloadLen = frameBuf.size() - 8;
          int numValues = payloadLen / 4;
          if (numValues == 320) {
          String line = getTimestamp();
          line += ",";
          for (int i = 0; i < numValues; i++) {
              uint32_t val = (uint32_t)frameBuf[4 + i*4] |
                  ((uint32_t)frameBuf[4 + i*4 + 1] << 8) |
                  ((uint32_t)frameBuf[4 + i*4 + 2] << 16) |
                  ((uint32_t)frameBuf[4 + i*4 + 3] << 24);
              line += String(val);
              if (i < numValues - 1) line += " ";
          }
          Serial.println(line);
      } else {
            Serial.print("Unexpected frame length: ");
            Serial.println(numValues);
          }
          inFrame = false;
        }
      }
    }
  } else {
    //Framed parser: collect bytes between header and trailer
    static bool inFrame = false;
    static std::vector<uint8_t> frameBuf;

    while (Serial2.available() > 0) {
      byte b = Serial2.read();

      //Find frame header 0xAA, depends on radar mode
      if (!inFrame && b == 0xAA) {
        frameBuf.clear();
        frameBuf.push_back(b);
        inFrame = true;
        continue;
      }

      
      if (inFrame) {
        frameBuf.push_back(b);

        //find trailer FD FC FB FA, depends on radar mode
        int n = frameBuf.size();
        if (n >= 4 &&
            frameBuf[n - 4] == 0xFD &&
            frameBuf[n - 3] == 0xFC &&
            frameBuf[n - 2] == 0xFB &&
            frameBuf[n - 1] == 0xFA) {
          parseDebugFrame(frameBuf);
          inFrame = false;
        }
      }
      
    }
  }
}

//Parse frame
void parseDebugFrame(const std::vector<uint8_t>& buf) {
  int payloadLen = buf.size() - 8;
  int numValues = payloadLen / 4; //should be 320
  if (numValues != 320) {
    Serial.print("Unexpected frame length: ");
    Serial.println(numValues);
    return;
  }

  for (int i = 0; i < numValues; i++) {
    uint32_t val = (uint32_t)buf[4 + i*4] |
                   ((uint32_t)buf[4 + i*4 + 1] << 8) |
                   ((uint32_t)buf[4 + i*4 + 2] << 16) |
                   ((uint32_t)buf[4 + i*4 + 3] << 24);
    int doppler = i / 16;
    int rangeGate = i % 16;
    rdmap[doppler][rangeGate] = val;
  }

  String ts = getTimestamp();
  if (ts == "Time Error") {
    ts = "Time not set yet";
  }
  Serial.print(ts + " ");
  Serial.println();

  for (int i = 0; i < 20; i++) {
    for (int j = 0; j < 16; j++) {
      Serial.print(rdmap[i][j]);
      Serial.print(" ");
    }
    Serial.println();
  }
  //delay(10000);
}

//Print all currently available bytes on Serial2 as a single-line hex dump.
void print_serial2_hex_line() {
  if (Serial2.available() == 0) {
    Serial.println("No Serial2 data available to dump.");
    return;
  }

  String ts = getTimestamp();
  if (ts == "Time Error") ts = "Time not set yet";

  Serial.print(ts);
  Serial.print(", ");

  //Read and print all available bytes as padded hex
  while (Serial2.available() > 0) {
    byte b = Serial2.read();
    if (b < 16) Serial.print('0');
    Serial.print(b, HEX);
    Serial.print(' ');
  }
  Serial.println();
}

