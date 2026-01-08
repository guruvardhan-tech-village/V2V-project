#!/usr/bin/env python3
"""
ESP32 Camera Frame Corruption Detection and Recovery Module

This module provides comprehensive frame corruption detection using multiple
validation methods and implements recovery mechanisms including retransmission
requests and frame reconstruction.

Requirements covered:
- 6.2: Detect corrupted frames using checksum validation
- 6.2: Request retransmission for corrupted frames
"""

import time
import zlib
import struct
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np


class CorruptionType(Enum):
    """Types of frame corruption"""
    CHECKSUM_MISMATCH = "checksum_mismatch"
    SIZE_MISMATCH = "size_mismatch"
    SEQUENCE_ERROR = "sequence_error"
    INVALID_JPEG_HEADER = "invalid_jpeg_header"
    INVALID_JPEG_FOOTER = "invalid_jpeg_footer"
    INCOMPLETE_FRAME = "incomplete_frame"
    PROTOCOL_ERROR = "protocol_error"
    DECODE_FAILURE = "decode_failure"


@dataclass
class CorruptionReport:
    """Report of frame corruption detection"""
    corruption_type: CorruptionType
    frame_sequence: int
    expected_value: Any
    actual_value: Any
    timestamp: float
    details: Dict[str, Any]
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


@dataclass
class RetransmissionRequest:
    """Request for frame retransmission"""
    sequence_number: int
    corruption_type: CorruptionType
    timestamp: float
    retry_count: int = 0
    max_retries: int = 3
    
    def is_expired(self, timeout: float = 5.0) -> bool:
        """Check if retransmission request has expired"""
        return time.time() - self.timestamp > timeout
    
    def can_retry(self) -> bool:
        """Check if more retries are allowed"""
        return self.retry_count < self.max_retries


class ESP32FrameValidator:
    """
    Comprehensive frame corruption detection and recovery system.
    
    Implements Requirements 6.2:
    - Detect corrupted frames using checksum validation
    - Request retransmission for corrupted frames
    """
    
    def __init__(self, 
                 enable_checksum_validation: bool = True,
                 enable_jpeg_validation: bool = True,
                 enable_sequence_validation: bool = True,
                 retransmission_timeout: float = 5.0,
                 max_retransmission_attempts: int = 3):
        """
        Initialize frame validator.
        
        Args:
            enable_checksum_validation: Enable CRC32 checksum validation
            enable_jpeg_validation: Enable JPEG format validation
            enable_sequence_validation: Enable sequence number validation
            retransmission_timeout: Timeout for retransmission requests
            max_retransmission_attempts: Maximum retransmission attempts per frame
        """
        self.enable_checksum_validation = enable_checksum_validation
        self.enable_jpeg_validation = enable_jpeg_validation
        self.enable_sequence_validation = enable_sequence_validation
        self.retransmission_timeout = retransmission_timeout
        self.max_retransmission_attempts = max_retransmission_attempts
        
        # Validation statistics
        self.validation_stats = {
            'frames_validated': 0,
            'frames_corrupted': 0,
            'corruption_by_type': {ct.value: 0 for ct in CorruptionType},
            'retransmissions_requested': 0,
            'retransmissions_successful': 0,
            'retransmissions_failed': 0
        }
        
        # Sequence tracking for validation
        self.expected_sequence = 0
        self.last_valid_sequence = -1
        self.sequence_gaps = []
        
        # Retransmission management
        self.pending_retransmissions: Dict[int, RetransmissionRequest] = {}
        self.corruption_history: List[CorruptionReport] = []
        
        # Frame reconstruction buffer for partial recovery
        self.partial_frames: Dict[int, Dict[str, Any]] = {}
        
        # Validation callbacks
        self.corruption_callback: Optional[callable] = None
        self.retransmission_callback: Optional[callable] = None
    
    def set_corruption_callback(self, callback: callable):
        """Set callback for corruption detection notifications"""
        self.corruption_callback = callback
    
    def set_retransmission_callback(self, callback: callable):
        """Set callback for retransmission requests"""
        self.retransmission_callback = callback
    
    def validate_frame(self, 
                      frame_data: bytes, 
                      sequence: int, 
                      expected_size: int = 0,
                      provided_checksum: str = "") -> Tuple[bool, Optional[CorruptionReport]]:
        """
        Comprehensive frame validation (Requirements 6.2).
        
        Args:
            frame_data: Raw frame data bytes
            sequence: Frame sequence number
            expected_size: Expected frame size
            provided_checksum: Checksum provided by sender
            
        Returns:
            Tuple of (is_valid, corruption_report)
        """
        self.validation_stats['frames_validated'] += 1
        
        # 1. Size validation
        if expected_size > 0 and len(frame_data) != expected_size:
            corruption = CorruptionReport(
                corruption_type=CorruptionType.SIZE_MISMATCH,
                frame_sequence=sequence,
                expected_value=expected_size,
                actual_value=len(frame_data),
                timestamp=time.time(),
                details={'frame_size': len(frame_data)}
            )
            return self._handle_corruption(corruption)
        
        # 2. Sequence validation
        if self.enable_sequence_validation:
            sequence_valid, sequence_corruption = self._validate_sequence(sequence)
            if not sequence_valid:
                return self._handle_corruption(sequence_corruption)
        
        # 3. Checksum validation
        if self.enable_checksum_validation and provided_checksum:
            checksum_valid, checksum_corruption = self._validate_checksum(
                frame_data, sequence, provided_checksum
            )
            if not checksum_valid:
                return self._handle_corruption(checksum_corruption)
        
        # 4. JPEG format validation
        if self.enable_jpeg_validation:
            jpeg_valid, jpeg_corruption = self._validate_jpeg_format(frame_data, sequence)
            if not jpeg_valid:
                return self._handle_corruption(jpeg_corruption)
        
        # 5. Frame completeness validation
        completeness_valid, completeness_corruption = self._validate_frame_completeness(
            frame_data, sequence
        )
        if not completeness_valid:
            return self._handle_corruption(completeness_corruption)
        
        # Frame is valid
        self._update_sequence_tracking(sequence)
        self._cleanup_successful_retransmission(sequence)
        
        return True, None
    
    def _validate_sequence(self, sequence: int) -> Tuple[bool, Optional[CorruptionReport]]:
        """Validate frame sequence number"""
        # Check for sequence gaps or duplicates
        if sequence <= self.last_valid_sequence:
            # Duplicate or out-of-order frame
            corruption = CorruptionReport(
                corruption_type=CorruptionType.SEQUENCE_ERROR,
                frame_sequence=sequence,
                expected_value=self.expected_sequence,
                actual_value=sequence,
                timestamp=time.time(),
                details={
                    'error_type': 'duplicate_or_out_of_order',
                    'last_valid_sequence': self.last_valid_sequence
                }
            )
            return False, corruption
        
        # Check for sequence gap
        if sequence > self.expected_sequence:
            # Missing frames detected
            gap_start = self.expected_sequence
            gap_end = sequence - 1
            self.sequence_gaps.append((gap_start, gap_end))
            
            corruption = CorruptionReport(
                corruption_type=CorruptionType.SEQUENCE_ERROR,
                frame_sequence=sequence,
                expected_value=self.expected_sequence,
                actual_value=sequence,
                timestamp=time.time(),
                details={
                    'error_type': 'sequence_gap',
                    'gap_start': gap_start,
                    'gap_end': gap_end,
                    'missing_frames': gap_end - gap_start + 1
                }
            )
            return False, corruption
        
        return True, None
    
    def _validate_checksum(self, 
                          frame_data: bytes, 
                          sequence: int, 
                          provided_checksum: str) -> Tuple[bool, Optional[CorruptionReport]]:
        """Validate frame checksum (Requirements 6.2)"""
        try:
            # Calculate CRC32 checksum
            calculated_checksum = format(zlib.crc32(frame_data) & 0xffffffff, '08X')
            
            if provided_checksum.upper() != calculated_checksum:
                corruption = CorruptionReport(
                    corruption_type=CorruptionType.CHECKSUM_MISMATCH,
                    frame_sequence=sequence,
                    expected_value=provided_checksum.upper(),
                    actual_value=calculated_checksum,
                    timestamp=time.time(),
                    details={
                        'frame_size': len(frame_data),
                        'checksum_algorithm': 'CRC32'
                    }
                )
                return False, corruption
            
            return True, None
            
        except Exception as e:
            corruption = CorruptionReport(
                corruption_type=CorruptionType.PROTOCOL_ERROR,
                frame_sequence=sequence,
                expected_value="valid_checksum",
                actual_value=f"checksum_error: {e}",
                timestamp=time.time(),
                details={'error': str(e)}
            )
            return False, corruption
    
    def _validate_jpeg_format(self, 
                             frame_data: bytes, 
                             sequence: int) -> Tuple[bool, Optional[CorruptionReport]]:
        """Validate JPEG format integrity"""
        if len(frame_data) < 4:
            corruption = CorruptionReport(
                corruption_type=CorruptionType.INCOMPLETE_FRAME,
                frame_sequence=sequence,
                expected_value="minimum_4_bytes",
                actual_value=len(frame_data),
                timestamp=time.time(),
                details={'frame_size': len(frame_data)}
            )
            return False, corruption
        
        # Check JPEG SOI (Start of Image) marker: 0xFF 0xD8
        if frame_data[0] != 0xFF or frame_data[1] != 0xD8:
            corruption = CorruptionReport(
                corruption_type=CorruptionType.INVALID_JPEG_HEADER,
                frame_sequence=sequence,
                expected_value="FF D8",
                actual_value=f"{frame_data[0]:02X} {frame_data[1]:02X}",
                timestamp=time.time(),
                details={'header_bytes': frame_data[:4].hex()}
            )
            return False, corruption
        
        # Check JPEG EOI (End of Image) marker: 0xFF 0xD9 at the end
        if len(frame_data) >= 2:
            if frame_data[-2] != 0xFF or frame_data[-1] != 0xD9:
                corruption = CorruptionReport(
                    corruption_type=CorruptionType.INVALID_JPEG_FOOTER,
                    frame_sequence=sequence,
                    expected_value="FF D9",
                    actual_value=f"{frame_data[-2]:02X} {frame_data[-1]:02X}",
                    timestamp=time.time(),
                    details={'footer_bytes': frame_data[-4:].hex()}
                )
                return False, corruption
        
        return True, None
    
    def _validate_frame_completeness(self, 
                                   frame_data: bytes, 
                                   sequence: int) -> Tuple[bool, Optional[CorruptionReport]]:
        """Validate frame completeness and structure"""
        # Check for minimum JPEG size
        if len(frame_data) < 100:  # Very small for a valid JPEG
            corruption = CorruptionReport(
                corruption_type=CorruptionType.INCOMPLETE_FRAME,
                frame_sequence=sequence,
                expected_value="minimum_100_bytes",
                actual_value=len(frame_data),
                timestamp=time.time(),
                details={'frame_size': len(frame_data), 'reason': 'too_small'}
            )
            return False, corruption
        
        # Check for reasonable maximum size (prevent memory issues)
        max_frame_size = 1024 * 1024  # 1MB limit
        if len(frame_data) > max_frame_size:
            corruption = CorruptionReport(
                corruption_type=CorruptionType.INCOMPLETE_FRAME,
                frame_sequence=sequence,
                expected_value=f"maximum_{max_frame_size}_bytes",
                actual_value=len(frame_data),
                timestamp=time.time(),
                details={'frame_size': len(frame_data), 'reason': 'too_large'}
            )
            return False, corruption
        
        return True, None
    
    def _handle_corruption(self, corruption: CorruptionReport) -> Tuple[bool, CorruptionReport]:
        """Handle detected frame corruption"""
        self.validation_stats['frames_corrupted'] += 1
        self.validation_stats['corruption_by_type'][corruption.corruption_type.value] += 1
        
        # Store corruption in history
        self.corruption_history.append(corruption)
        
        # Keep only last 100 corruption reports
        if len(self.corruption_history) > 100:
            self.corruption_history = self.corruption_history[-100:]
        
        # Notify corruption callback
        if self.corruption_callback:
            try:
                self.corruption_callback(corruption)
            except Exception as e:
                print(f"⚠️ Error in corruption callback: {e}")
        
        # Request retransmission if appropriate
        if self._should_request_retransmission(corruption):
            self._request_retransmission(corruption)
        
        return False, corruption
    
    def _should_request_retransmission(self, corruption: CorruptionReport) -> bool:
        """Determine if retransmission should be requested"""
        # Don't request retransmission for sequence errors (would cause more confusion)
        if corruption.corruption_type == CorruptionType.SEQUENCE_ERROR:
            return False
        
        # Don't request if already pending for this sequence
        if corruption.frame_sequence in self.pending_retransmissions:
            return False
        
        # Don't request for very old frames
        if corruption.frame_sequence < self.last_valid_sequence - 10:
            return False
        
        return True
    
    def _request_retransmission(self, corruption: CorruptionReport):
        """Request frame retransmission (Requirements 6.2)"""
        request = RetransmissionRequest(
            sequence_number=corruption.frame_sequence,
            corruption_type=corruption.corruption_type,
            timestamp=time.time(),
            max_retries=self.max_retransmission_attempts
        )
        
        self.pending_retransmissions[corruption.frame_sequence] = request
        self.validation_stats['retransmissions_requested'] += 1
        
        # Notify retransmission callback
        if self.retransmission_callback:
            try:
                self.retransmission_callback(request)
            except Exception as e:
                print(f"⚠️ Error in retransmission callback: {e}")
        
        print(f"📤 Requesting retransmission for frame {corruption.frame_sequence} "
              f"(corruption: {corruption.corruption_type.value})")
    
    def _update_sequence_tracking(self, sequence: int):
        """Update sequence tracking for valid frames"""
        self.last_valid_sequence = sequence
        self.expected_sequence = sequence + 1
    
    def _cleanup_successful_retransmission(self, sequence: int):
        """Clean up successful retransmission"""
        if sequence in self.pending_retransmissions:
            del self.pending_retransmissions[sequence]
            self.validation_stats['retransmissions_successful'] += 1
            print(f"✅ Retransmission successful for frame {sequence}")
    
    def handle_retransmission_timeout(self):
        """Handle expired retransmission requests"""
        current_time = time.time()
        expired_requests = []
        
        for seq, request in self.pending_retransmissions.items():
            if request.is_expired(self.retransmission_timeout):
                if request.can_retry():
                    # Retry the request
                    request.retry_count += 1
                    request.timestamp = current_time
                    
                    if self.retransmission_callback:
                        try:
                            self.retransmission_callback(request)
                        except Exception as e:
                            print(f"⚠️ Error in retransmission retry callback: {e}")
                    
                    print(f"🔄 Retrying retransmission request for frame {seq} "
                          f"(attempt {request.retry_count}/{request.max_retries})")
                else:
                    # Give up on this frame
                    expired_requests.append(seq)
                    self.validation_stats['retransmissions_failed'] += 1
                    print(f"❌ Retransmission failed for frame {seq} after {request.retry_count} attempts")
        
        # Remove expired requests
        for seq in expired_requests:
            del self.pending_retransmissions[seq]
    
    def get_retransmission_command(self, sequence: int) -> str:
        """Generate retransmission command for ESP32"""
        return f"RETRANSMIT|seq:{sequence:03d}"
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get comprehensive validation statistics"""
        stats = self.validation_stats.copy()
        
        # Add derived statistics
        if stats['frames_validated'] > 0:
            stats['corruption_rate'] = (stats['frames_corrupted'] / stats['frames_validated']) * 100
        else:
            stats['corruption_rate'] = 0.0
        
        stats['pending_retransmissions'] = len(self.pending_retransmissions)
        stats['sequence_gaps'] = len(self.sequence_gaps)
        stats['last_valid_sequence'] = self.last_valid_sequence
        stats['expected_sequence'] = self.expected_sequence
        
        return stats
    
    def get_corruption_summary(self) -> Dict[str, Any]:
        """Get corruption summary for analysis"""
        recent_corruptions = self.corruption_history[-10:] if self.corruption_history else []
        
        return {
            'total_corruptions': len(self.corruption_history),
            'recent_corruptions': [
                {
                    'type': c.corruption_type.value,
                    'sequence': c.frame_sequence,
                    'timestamp': c.timestamp,
                    'details': c.details
                }
                for c in recent_corruptions
            ],
            'corruption_by_type': self.validation_stats['corruption_by_type'],
            'pending_retransmissions': [
                {
                    'sequence': req.sequence_number,
                    'type': req.corruption_type.value,
                    'retry_count': req.retry_count,
                    'age': time.time() - req.timestamp
                }
                for req in self.pending_retransmissions.values()
            ]
        }
    
    def reset_validation_state(self):
        """Reset validation state for fresh start"""
        self.expected_sequence = 0
        self.last_valid_sequence = -1
        self.sequence_gaps.clear()
        self.pending_retransmissions.clear()
        self.partial_frames.clear()
        
        # Reset statistics
        self.validation_stats = {
            'frames_validated': 0,
            'frames_corrupted': 0,
            'corruption_by_type': {ct.value: 0 for ct in CorruptionType},
            'retransmissions_requested': 0,
            'retransmissions_successful': 0,
            'retransmissions_failed': 0
        }
        
        print("🔄 Frame validation state reset")


# Global validator instance
_global_validator: Optional[ESP32FrameValidator] = None


def get_global_validator() -> ESP32FrameValidator:
    """Get or create global frame validator instance"""
    global _global_validator
    if _global_validator is None:
        _global_validator = ESP32FrameValidator()
    return _global_validator


def reset_global_validator():
    """Reset global validator"""
    global _global_validator
    if _global_validator:
        _global_validator.reset_validation_state()
    _global_validator = None