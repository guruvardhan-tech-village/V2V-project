#ifndef CONFIG_H
#define CONFIG_H

// Serial Communication Configuration
#define SERIAL_BAUD_RATE 921600
#define SERIAL_TIMEOUT_MS 100

// Frame Protocol Configuration
#define FRAME_START_MARKER "FRAME_START"
#define FRAME_END_MARKER "FRAME_END"
#define STATUS_MARKER "STATUS"
#define CONFIG_MARKER "CONFIG"
#define CONFIG_ACK_MARKER "CONFIG_ACK"

// Protocol Message Delimiters
#define PROTOCOL_DELIMITER "|"
#define MESSAGE_TERMINATOR "\n"

// Protocol Field Names
#define FIELD_SIZE "size"
#define FIELD_SEQUENCE "seq"
#define FIELD_CHECKSUM "checksum"
#define FIELD_TIMESTAMP "timestamp"
#define FIELD_FPS "fps"
#define FIELD_TEMP "temp"
#define FIELD_FREE_HEAP "free_heap"

// Camera Default Settings
#define DEFAULT_RESOLUTION FRAMESIZE_VGA  // 640x480
#define DEFAULT_FPS 15
#define DEFAULT_JPEG_QUALITY 50

// Chunk transmission configuration
#define CHUNK_HEADER_MARKER "CHUNK"
#define FIELD_CHUNK_INDEX "index"
#define FIELD_CHUNK_TOTAL "total"
#define FIELD_CHUNK_SIZE "size"

// Chunk information structure
struct ChunkInfo {
  uint16_t index;
  uint16_t total;
  uint16_t size;
  uint16_t frameSequence;
  
  ChunkInfo(uint16_t idx, uint16_t totalChunks, uint16_t chunkSize, uint16_t frameSec)
    : index(idx), total(totalChunks), size(chunkSize), frameSequence(frameSec) {}
  
  String toProtocolMessage() const {
    ProtocolMessage msg(CHUNK_HEADER_MARKER);
    msg.addField(FIELD_CHUNK_INDEX, index);
    msg.addField(FIELD_CHUNK_TOTAL, total);
    msg.addField(FIELD_CHUNK_SIZE, size);
    msg.addField(FIELD_SEQUENCE, frameSequence);
    return msg.toString();
  }
};

// Performance Settings
#define FRAME_BUFFER_SIZE 65536
#define MAX_FRAME_SIZE 32768
#define CHUNK_SIZE 1024
#define STATUS_INTERVAL_MS 5000

// Frame Rate Limits
#define MIN_FPS 5
#define MAX_FPS 30

// JPEG Quality Limits
#define MIN_JPEG_QUALITY 10
#define MAX_JPEG_QUALITY 63

// Memory Management
#define PSRAM_REQUIRED true
#define FB_COUNT_WITH_PSRAM 2
#define FB_COUNT_WITHOUT_PSRAM 1

// Camera Sensor Settings
#define XCLK_FREQ_HZ 20000000
#define PIXEL_FORMAT PIXFORMAT_JPEG

// Error Handling
#define MAX_INIT_RETRIES 3
#define CAPTURE_TIMEOUT_MS 5000
#define MAX_TRANSMISSION_RETRIES 3
#define RETRY_DELAY_MS 100
#define ACK_TIMEOUT_MS 1000

// Error Response Messages
#define ERROR_MARKER "ERROR"
#define ACK_MARKER "ACK"
#define NACK_MARKER "NACK"
#define RETRY_MARKER "RETRY"

#endif // CONFIG_H