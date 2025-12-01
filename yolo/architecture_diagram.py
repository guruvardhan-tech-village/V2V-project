#!/usr/bin/env python3
"""
Generate architecture diagram using matplotlib
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
import matplotlib.patches as mpatches

def create_architecture_diagram():
    """Create a block diagram of the system architecture."""
    
    fig, ax = plt.subplots(1, 1, figsize=(16, 12))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    # Colors
    vehicle_color = '#e1f5ff'
    cloud_color = '#fff3e0'
    nearby_color = '#f3e5f5'
    arrow_color = '#333333'
    
    # === VEHICLE A ===
    vehicle_box = FancyBboxPatch((0.5, 6.5), 3, 2.5, 
                                  boxstyle="round,pad=0.1", 
                                  edgecolor='#01579b', 
                                  facecolor=vehicle_color,
                                  linewidth=2)
    ax.add_patch(vehicle_box)
    ax.text(2, 8.7, '🚗 VEHICLE A (YOUR CAR)', 
            ha='center', va='center', fontsize=12, fontweight='bold')
    
    # ESP32-CAM
    cam_box = Rectangle((0.7, 7.5), 0.8, 0.6, 
                        edgecolor='#01579b', facecolor='white', linewidth=1.5)
    ax.add_patch(cam_box)
    ax.text(1.1, 7.8, 'ESP32-CAM\nMJPEG', ha='center', va='center', fontsize=8)
    
    # Laptop
    lap_box = Rectangle((1.7, 7.5), 0.8, 0.6, 
                        edgecolor='#01579b', facecolor='white', linewidth=1.5)
    ax.add_patch(lap_box)
    ax.text(2.1, 7.8, '💻 Laptop\nYOLOv8', ha='center', va='center', fontsize=8)
    
    # ESP32
    mcu_box = Rectangle((2.7, 7.5), 0.8, 0.6, 
                        edgecolor='#01579b', facecolor='white', linewidth=1.5)
    ax.add_patch(mcu_box)
    ax.text(3.1, 7.8, 'ESP32\nGPS+LoRa', ha='center', va='center', fontsize=8)
    
    # Android App A
    app_box = Rectangle((1.2, 6.7), 1.6, 0.5, 
                        edgecolor='#01579b', facecolor='white', linewidth=1.5)
    ax.add_patch(app_box)
    ax.text(2, 6.95, '📱 Android App A', ha='center', va='center', fontsize=9, fontweight='bold')
    
    # Arrows in Vehicle A
    ax.arrow(1.5, 7.5, 0.2, 0, head_width=0.05, head_length=0.05, 
             fc=arrow_color, ec=arrow_color, length_includes_head=True)
    ax.arrow(2.5, 7.5, 0.2, 0, head_width=0.05, head_length=0.05, 
             fc=arrow_color, ec=arrow_color, length_includes_head=True)
    ax.arrow(2.1, 7.2, 0, -0.2, head_width=0.05, head_length=0.05, 
             fc=arrow_color, ec=arrow_color, length_includes_head=True)
    ax.arrow(3.1, 7.2, -0.9, -0.2, head_width=0.05, head_length=0.05, 
             fc=arrow_color, ec=arrow_color, length_includes_head=True)
    
    # === NEARBY VEHICLES ===
    nearby_box = FancyBboxPatch((0.5, 4), 3, 1.5, 
                                 boxstyle="round,pad=0.1", 
                                 edgecolor='#4a148c', 
                                 facecolor=nearby_color,
                                 linewidth=2)
    ax.add_patch(nearby_box)
    ax.text(2, 5.4, '🚙 OTHER NEARBY VEHICLES', 
            ha='center', va='center', fontsize=12, fontweight='bold')
    
    # LoRa Receiver
    lora_box = Rectangle((1, 4.3), 0.8, 0.6, 
                         edgecolor='#4a148c', facecolor='white', linewidth=1.5)
    ax.add_patch(lora_box)
    ax.text(1.4, 4.6, 'ESP32\nLoRa', ha='center', va='center', fontsize=8)
    
    # Nearby Apps
    apps_box = Rectangle((2.2, 4.3), 0.8, 0.6, 
                         edgecolor='#4a148c', facecolor='white', linewidth=1.5)
    ax.add_patch(apps_box)
    ax.text(2.6, 4.6, '📱 Android\nApps', ha='center', va='center', fontsize=8)
    
    # Arrow in Nearby Vehicles
    ax.arrow(1.8, 4.6, 0.4, 0, head_width=0.05, head_length=0.05, 
             fc=arrow_color, ec=arrow_color, length_includes_head=True)
    
    # Arrow from Vehicle A to Nearby
    ax.arrow(3.1, 6.5, 0, -1, head_width=0.1, head_length=0.1, 
             fc='#e65100', ec='#e65100', linewidth=2, length_includes_head=True)
    ax.text(3.3, 5.5, 'LoRa\nBroadcast', ha='left', va='center', fontsize=8, 
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
    
    # === CLOUD ===
    cloud_box = FancyBboxPatch((5, 4), 4.5, 5, 
                                boxstyle="round,pad=0.1", 
                                edgecolor='#e65100', 
                                facecolor=cloud_color,
                                linewidth=2)
    ax.add_patch(cloud_box)
    ax.text(7.25, 8.7, '☁️ GOOGLE CLOUD (Free-tier)', 
            ha='center', va='center', fontsize=12, fontweight='bold')
    
    # Firebase Auth
    auth_box = Rectangle((5.3, 7.8), 1, 0.5, 
                         edgecolor='#e65100', facecolor='white', linewidth=1.5)
    ax.add_patch(auth_box)
    ax.text(5.8, 8.05, 'Firebase\nAuth', ha='center', va='center', fontsize=8)
    
    # Firestore
    db_box = Rectangle((6.5, 7.8), 1, 0.5, 
                       edgecolor='#e65100', facecolor='white', linewidth=1.5)
    ax.add_patch(db_box)
    ax.text(7, 8.05, 'Firestore\nDatabase', ha='center', va='center', fontsize=8)
    
    # Cloud Storage
    store_box = Rectangle((7.7, 7.8), 1, 0.5, 
                          edgecolor='#e65100', facecolor='white', linewidth=1.5)
    ax.add_patch(store_box)
    ax.text(8.2, 8.05, 'Cloud\nStorage', ha='center', va='center', fontsize=8)
    
    # Cloud Run
    run_box = Rectangle((5.8, 6.8), 1.8, 0.6, 
                        edgecolor='#e65100', facecolor='white', linewidth=1.5)
    ax.add_patch(run_box)
    ax.text(7.7, 7.1, 'Cloud Run / Functions', ha='center', va='center', fontsize=9, fontweight='bold')
    
    # Pub/Sub
    pub_box = Rectangle((7.8, 6.8), 1, 0.6, 
                        edgecolor='#e65100', facecolor='white', linewidth=1.5)
    ax.add_patch(pub_box)
    ax.text(8.3, 7.1, 'Pub/Sub', ha='center', va='center', fontsize=8)
    
    # FCM
    fcm_box = Rectangle((6, 5.5), 2.5, 0.6, 
                        edgecolor='#e65100', facecolor='white', linewidth=1.5)
    ax.add_patch(fcm_box)
    ax.text(7.25, 5.8, 'Firebase Cloud Messaging (FCM)', 
            ha='center', va='center', fontsize=9, fontweight='bold')
    
    # Arrows in Cloud
    ax.arrow(6.3, 8.05, 0.2, 0, head_width=0.03, head_length=0.03, 
             fc=arrow_color, ec=arrow_color, length_includes_head=True)
    ax.arrow(7.5, 8.05, 0.2, 0, head_width=0.03, head_length=0.03, 
             fc=arrow_color, ec=arrow_color, length_includes_head=True)
    ax.arrow(7, 7.8, 0, -0.3, head_width=0.05, head_length=0.05, 
             fc=arrow_color, ec=arrow_color, length_includes_head=True)
    ax.arrow(7.7, 7.1, 0.1, -0.3, head_width=0.05, head_length=0.05, 
             fc=arrow_color, ec=arrow_color, length_includes_head=True)
    ax.arrow(7, 7.5, 0.25, -0.7, head_width=0.05, head_length=0.05, 
             fc=arrow_color, ec=arrow_color, length_includes_head=True)
    
    # Arrows from Vehicle A to Cloud
    ax.arrow(3.5, 7.8, 1.5, 0.2, head_width=0.1, head_length=0.1, 
             fc='#e65100', ec='#e65100', linewidth=2, length_includes_head=True)
    ax.text(4.5, 8.2, 'HTTPS', ha='center', va='center', fontsize=8,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
    
    ax.arrow(3.5, 7.5, 1.5, -0.1, head_width=0.1, head_length=0.1, 
             fc='#e65100', ec='#e65100', linewidth=2, length_includes_head=True)
    ax.text(4.5, 7.2, 'HTTPS', ha='center', va='center', fontsize=8,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
    
    ax.arrow(2.8, 6.7, 2.2, -0.5, head_width=0.1, head_length=0.1, 
             fc='#e65100', ec='#e65100', linewidth=2, length_includes_head=True)
    ax.text(4, 6, 'SDK', ha='center', va='center', fontsize=8,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
    
    # Arrow from Cloud to App
    ax.arrow(7.25, 5.5, -4.75, 1.2, head_width=0.1, head_length=0.1, 
             fc='#e65100', ec='#e65100', linewidth=2, length_includes_head=True)
    ax.text(4, 6.5, 'FCM\nNotifications', ha='center', va='center', fontsize=8,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
    
    # Arrow from Cloud to Nearby
    ax.arrow(7.25, 4.5, -3.75, -0.3, head_width=0.1, head_length=0.1, 
             fc='#e65100', ec='#e65100', linewidth=2, length_includes_head=True)
    
    # Title
    ax.text(5, 9.5, 'Vehicle Accident Detection System Architecture', 
            ha='center', va='center', fontsize=16, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig('system_architecture.png', dpi=300, bbox_inches='tight')
    plt.savefig('system_architecture.pdf', bbox_inches='tight')
    print("✅ Architecture diagram saved as 'system_architecture.png' and 'system_architecture.pdf'")
    plt.show()

if __name__ == "__main__":
    create_architecture_diagram()

