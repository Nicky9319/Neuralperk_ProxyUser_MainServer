import asyncio
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import threading
import nest_asyncio

from fastapi import FastAPI, Response, Request, HTTPException, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from fastapi.responses import JSONResponse

import uvicorn
import httpx
import json
from datetime import datetime
import uuid
import hashlib
import secrets

import asyncio
import aio_pika


import sys
import os

from dotenv import load_dotenv
load_dotenv()

# Enable nested event loops for Streamlit
nest_asyncio.apply()


class AdminPanelStreamlit:
    """
    Streamlit-based Admin Panel for monitoring and managing the system.
    
    This class provides a web-based interface for administrators to monitor
    and control the User Manager and Session Supervisor services. It includes
    authentication, real-time dashboards, and interactive controls.
    """
    
    def __init__(self):
        """Initialize the Admin Panel with service configurations."""
        # Service URLs configuration
        user_manager_env_url = os.getenv("USER_MANAGER_SERVICE", "").strip()
        if not user_manager_env_url or not (user_manager_env_url.startswith("http://") or user_manager_env_url.startswith("https://")):
            self.user_manager_service_url = "http://127.0.0.1:7000"
        else:
            self.user_manager_service_url = user_manager_env_url
            
        session_supervisor_env_url = os.getenv("SESSION_SUPERVISOR_SERVICE", "").strip()
        if not session_supervisor_env_url or not (session_supervisor_env_url.startswith("http://") or session_supervisor_env_url.startswith("https://")):
            self.session_supervisor_service_url = "http://127.0.0.1:7500"
        else:
            self.session_supervisor_service_url = session_supervisor_env_url
            
        user_service_env_url = os.getenv("USER_SERVICE", "").strip()
        if not user_service_env_url or not (user_service_env_url.startswith("http://") or user_service_env_url.startswith("https://")):
            self.user_service_url = "http://127.0.0.1:8500"
        else:
            self.user_service_url = user_service_env_url
            
        vastai_service_env_url = os.getenv("VASTAI_SERVICE", "").strip()
        if not vastai_service_env_url or not (vastai_service_env_url.startswith("http://") or vastai_service_env_url.startswith("https://")):
            self.vastai_service_url = "http://127.0.0.1:6000"
        else:
            self.vastai_service_url = vastai_service_env_url
        
        # HTTP client for service communication
        self.http_client = httpx.AsyncClient(timeout=30.0)  # Default timeout for most services
        
        # Debug: Print service URLs
        print(f"User Manager Service URL: {self.user_manager_service_url}")
        print(f"Session Supervisor Service URL: {self.session_supervisor_service_url}")
        print(f"VastAI Service URL: {self.vastai_service_url}")
        print(f"Note: VastAI operations use extended timeouts (45-60s) due to CLI operations")
        
        # Authentication credentials
        self.admin_username = "admin"
        self.admin_password = "password"
        
        # Initialize session state
        if 'authenticated' not in st.session_state:
            st.session_state.authenticated = False
        if 'auto_refresh' not in st.session_state:
            st.session_state.auto_refresh = False
        if 'refresh_interval' not in st.session_state:
            st.session_state.refresh_interval = 5
    
    def authenticate_user(self, username, password):
        """
        Authenticate user credentials.
        
        Args:
            username (str): Entered username
            password (str): Entered password
            
        Returns:
            bool: True if authentication successful, False otherwise
        """
        return username == self.admin_username and password == self.admin_password
    
    def login_page(self):
        """
        Display the login page for authentication.
        """
        st.set_page_config(
            page_title="Admin Panel - Login",
            page_icon="🔐",
            layout="wide"
        )
        
        st.title("🔐 Admin Panel Login")
        st.markdown("---")
        
        # Center the login form
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.subheader("Please enter your credentials")
            
            with st.form("login_form"):
                username = st.text_input("Username", placeholder="Enter username")
                password = st.text_input("Password", type="password", placeholder="Enter password")
                submit_button = st.form_submit_button("Login", use_container_width=True)
                
                if submit_button:
                    if self.authenticate_user(username, password):
                        st.session_state.authenticated = True
                        st.success("Login successful! Redirecting...")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
            
            st.info("💡 **Default Credentials:**\n- Username: `admin`\n- Password: `password`")
    
    async def get_user_manager_overview(self):
        """Get User Manager overview data."""
        try:
            response = await self.http_client.get(f"{self.user_manager_service_url}/api/user-manager/get-overview")
            if response.status_code == 200:
                return response.json()
            return {}
        except Exception as e:
            st.error(f"Error fetching User Manager data: {str(e)}")
            return {}
    
    async def get_session_supervisor_info(self):
        """Get all Session Supervisor information."""
        try:
            url = f"{self.session_supervisor_service_url}/api/session-supervisor-service/get-all-supervisor-information"
            print(f"Making request to: {url}")
            response = await self.http_client.get(url)
            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"Session Supervisor service returned status {response.status_code}")
                return []
        except Exception as e:
            st.error(f"Error fetching Session Supervisor data: {str(e)}")
            print(f"Full error details: {e}")
            return []
    
    async def get_specific_supervisor_overview(self, customer_id):
        """Get specific session supervisor overview."""
        try:
            response = await self.http_client.get(f"{self.session_supervisor_service_url}/api/session-supervisor-service/get-session-supervisor-overview/{customer_id}")
            if response.status_code == 200:
                return response.json()
            return {}
        except Exception as e:
            st.error(f"Error fetching supervisor overview: {str(e)}")
            return {}
    
    async def get_total_connected_user_count(self):
        try:
            response = await self.http_client.get(f"{self.user_service_url}/api/user-service/user/connected-users-count")
            if response.status_code == 200:
                data = response.json()
                print(data)
                return data.get("total_connected_users", 0)
            else:
                st.error(f"Failed to fetch connected user count: HTTP {response.status_code}")
                return 0
        except Exception as e:
            st.error(f"Error fetching connected user count: {str(e)}")
            return 0

    async def get_supervisor_user_count(self, customer_id):
        """Get user count for a specific supervisor."""
        try:
            response = await self.http_client.get(f"{self.session_supervisor_service_url}/api/session-supervisor-service/get-user-count/{customer_id}")
            if response.status_code == 200:
                return response.json()
            return {}
        except Exception as e:
            st.error(f"Error fetching user count: {str(e)}")
            return {}
    
    async def set_supervisor_user_count(self, customer_id, user_count):
        """Set user count for a specific supervisor."""
        try:
            response = await self.http_client.post(f"{self.session_supervisor_service_url}/api/session-supervisor-service/set-user-count/{customer_id}/{user_count}")
            if response.status_code == 200:
                return response.json()
            return False
        except Exception as e:
            st.error(f"Error setting user count: {str(e)}")
            return False
            
    async def get_vastai_instances(self):
        """Get list of all active VastAI instances."""
        try:
            # Create a client with increased timeout specifically for VastAI operations
            vastai_client = httpx.AsyncClient(timeout=45.0)  # Extended timeout to 45 seconds
            
            response = await vastai_client.get(f"{self.vastai_service_url}/api/vastai-service/instance/list-of-instances")
            
            # Close the client after use
            await vastai_client.aclose()
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and "instances" in data:
                    instances = data["instances"]
                    # Validate the instances array to ensure no None objects
                    return [instance for instance in instances if instance is not None]
            return []
        except httpx.TimeoutException:
            st.error("Timeout while fetching VastAI instances. VastAI operations can take longer than usual.")
            return []
        except Exception as e:
            st.error(f"Error fetching VastAI instances: {str(e)}")
            return []
    
    async def get_vastai_instance_info(self, instance_id):
        """Get detailed information about a specific VastAI instance."""
        try:
            # Create a client with increased timeout specifically for VastAI operations
            # VastAI operations can take longer as they involve CLI calls
            vastai_client = httpx.AsyncClient(timeout=60.0)  # Extended timeout to 60 seconds
            
            response = await vastai_client.get(f"{self.vastai_service_url}/api/vastai-service/instance/information/{instance_id}")
            
            # Close the client after use
            await vastai_client.aclose()
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and "instance" in data:
                    return data["instance"]
            return None
        except httpx.TimeoutException:
            st.error(f"Timeout while fetching VastAI instance info for {instance_id}. VastAI operations can take longer than usual.")
            return None
        except Exception as e:
            st.error(f"Error fetching VastAI instance info: {str(e)}")
            return None
    
    def main_dashboard(self):
        """
        Main dashboard interface after authentication.
        """
        st.set_page_config(
            page_title="Admin Panel Dashboard",
            page_icon="🔧",
            layout="wide"
        )
        
        # Header
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.title("🔧 System Admin Panel")
        with col2:
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()
        with col3:
            if st.button("🚪 Logout", use_container_width=True):
                st.session_state.authenticated = False
                st.rerun()
        
        st.markdown("---")
        
        # Auto-refresh settings (disabled)
        with st.expander("⚙️ Settings"):
            col1, col2 = st.columns(2)
            with col1:
                st.session_state.auto_refresh = st.checkbox("Auto-refresh (Disabled)", value=False, disabled=True)
            with col2:
                st.session_state.refresh_interval = st.slider("Refresh interval (seconds)", 1, 30, st.session_state.refresh_interval, disabled=True)
            st.info("ℹ️ Auto-refresh has been disabled. Use the refresh button to update data manually.")
        
        # Main content tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 System Overview", 
            "👥 User Manager", 
            "🎬 Session Supervisors", 
            "⚡ Quick Actions",
            "🖥️ Vast AI Instances"
        ])
        
        with tab1:
            asyncio.run(self.render_system_overview())
        
        with tab2:
            asyncio.run(self.render_user_manager_section())
        
        with tab3:
            asyncio.run(self.render_session_supervisor_section())
        
        with tab4:
            asyncio.run(self.render_quick_actions())
            
        with tab5:
            asyncio.run(self.render_vastai_instances())
            
        
        
        # Auto-refresh disabled - only manual refresh via buttons
    
    async def render_system_overview(self):
        """Render the system overview dashboard."""
        st.subheader("📊 System Overview")
        
        # Get data from both services
        user_manager_data = await self.get_user_manager_overview()
        session_supervisor_data = await self.get_session_supervisor_info()
        total_connected_users = await self.get_total_connected_user_count()
        
        # Summary metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            total_sessions = len(user_manager_data.get("activeSessions", []))
            st.metric("Active Sessions", total_sessions)
        
        with col2:
            idle_users = len(user_manager_data.get("idle_users", []))
            st.metric("Idle Users", idle_users)
        
        with col3:
            demand_requests = len(user_manager_data.get("user_demand_queue", []))
            st.metric("Demand Requests", demand_requests)
        
        with col4:
            supervisors = len(session_supervisor_data)
            st.metric("Session Supervisors", supervisors)
        
        with col5:
            total_users = total_connected_users
            st.metric("Connected Users", total_users)
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            # User distribution pie chart
            if user_manager_data:
                total_users = len(user_manager_data.get("userToSupervisorIdMapping", {}))
                idle_users = len(user_manager_data.get("idle_users", []))
                active_users = total_users - idle_users
                
                fig = px.pie(
                    values=[active_users, idle_users],
                    names=["Active Users", "Idle Users"],
                    title="User Distribution",
                    color_discrete_sequence=["#FF6B6B", "#4ECDC4"]
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Session status distribution
            if session_supervisor_data:
                status_counts = {}
                for supervisor in session_supervisor_data:
                    status = supervisor.get("session_status", "unknown")
                    status_counts[status] = status_counts.get(status, 0) + 1
                
                if status_counts:
                    fig = px.bar(
                        x=list(status_counts.keys()),
                        y=list(status_counts.values()),
                        title="Session Status Distribution",
                        color=list(status_counts.values()),
                        color_continuous_scale="viridis"
                    )
                    st.plotly_chart(fig, use_container_width=True)
    
    async def render_user_manager_section(self):
        """Render the User Manager section."""
        st.subheader("👥 User Manager")
        
        user_manager_data = await self.get_user_manager_overview()
        
        if not user_manager_data:
            st.warning("No User Manager data available")
            return
        
        # User to Supervisor Mapping
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**User to Supervisor Mapping:**")
            mapping = user_manager_data.get("userToSupervisorIdMapping", {})
            if mapping:
                df = pd.DataFrame(list(mapping.items()), columns=["User ID", "Supervisor ID"])
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No user mappings found")
        
        with col2:
            st.write("**Idle Users:**")
            idle_users = user_manager_data.get("idle_users", [])
            if idle_users:
                df = pd.DataFrame(idle_users, columns=["User ID"])
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No idle users")
        
        # Demand Queue
        st.write("**User Demand Queue:**")
        demand_queue = user_manager_data.get("user_demand_queue", [])
        if demand_queue:
            df = pd.DataFrame(demand_queue)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No pending demands")
        
        # Active Sessions
        st.write("**Active Sessions:**")
        active_sessions = user_manager_data.get("activeSessions", [])
        if active_sessions:
            df = pd.DataFrame(active_sessions, columns=["Session ID"])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No active sessions")
    
    async def render_session_supervisor_section(self):
        """Render the Session Supervisor section."""
        st.subheader("🎬 Session Supervisors")
        
        session_supervisor_data = await self.get_session_supervisor_info()
        
        if not session_supervisor_data:
            st.warning("No Session Supervisor data available")
            return
        
        # Display session supervisors in cards
        for i, supervisor in enumerate(session_supervisor_data):
            with st.expander(f"Session Supervisor {i+1} - {supervisor.get('session_id', 'Unknown')}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Object ID:** {supervisor.get('object_id', 'N/A')}")
                    st.write(f"**Session ID:** {supervisor.get('session_id', 'N/A')}")
                    st.write(f"**Status:** {supervisor.get('session_status', 'N/A')}")
                
                with col2:
                    st.write(f"**Number of Users:** {supervisor.get('number_of_users', 'N/A')}")
                    st.write(f"**Routing Key:** {supervisor.get('session_routing_key', 'N/A')}")
                
                # User count management
                st.write("**Manage User Count:**")
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    # Allow zero as a valid initial value
                    initial_count = supervisor.get('number_of_users', 0) or 0
                    if initial_count < 0:
                        initial_count = 0
                    new_user_count = st.number_input(
                        "New User Count",
                        min_value=0,
                        max_value=20,
                        value=initial_count,
                        key=f"user_count_{i}"
                    )
                
                with col2:
                    if st.button("Update", key=f"update_{i}"):
                        # Use explicit customer_id returned by the API instead of session_id
                        customer_id = supervisor.get('customer_id', '')
                        result = await self.set_supervisor_user_count(customer_id, new_user_count)
                        if result:
                            st.success("User count updated!")
                            st.rerun()
                        else:
                            st.error("Failed to update user count")
    
    async def render_quick_actions(self):
        """Render quick actions panel."""
        st.subheader("⚡ Quick Actions")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Session Supervisor Actions:**")
            
            # Get specific supervisor info
            customer_id = st.text_input("Customer ID", placeholder="Enter customer ID")
            
            if st.button("Get Supervisor Info"):
                if customer_id:
                    info = await self.get_specific_supervisor_overview(customer_id)
                    if info:
                        st.json(info)
                    else:
                        st.error("No information found for this customer ID")
                else:
                    st.warning("Please enter a customer ID")
            
            # User count management
            st.write("**User Count Management:**")
            col1_1, col1_2 = st.columns(2)
            with col1_1:
                manage_customer_id = st.text_input("Customer ID for User Count", placeholder="Enter customer ID")
            with col1_2:
                user_count = st.number_input("User Count", min_value=1, max_value=20, value=1)
            
            if st.button("Set User Count"):
                if manage_customer_id:
                    result = await self.set_supervisor_user_count(manage_customer_id, user_count)
                    if result:
                        st.success(f"User count set to {user_count} for customer {manage_customer_id}")
                    else:
                        st.error("Failed to set user count")
                else:
                    st.warning("Please enter a customer ID")
        
        with col2:
            st.write("**System Information:**")
            
            if st.button("Refresh All Data"):
                st.success("Data refreshed!")
                st.rerun()
            
            if st.button("Export System Status"):
                # Get all data
                user_manager_data = await self.get_user_manager_overview()
                session_supervisor_data = await self.get_session_supervisor_info()
                
                system_data = {
                    "timestamp": datetime.now().isoformat(),
                    "user_manager": user_manager_data,
                    "session_supervisors": session_supervisor_data
                }
                
                st.download_button(
                    label="Download JSON",
                    data=json.dumps(system_data, indent=2),
                    file_name=f"system_status_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
    
    async def render_vastai_instances(self):
        """Render the Vast AI Instances tab."""
        st.subheader("🖥️ Vast AI Instances")

        # Show loading indicator while fetching data
        with st.spinner("Fetching VastAI instances..."):
            # Get real instance data from the VastAI service
            instances = await self.get_vastai_instances()
        
        if not instances:
            st.warning("No VastAI instances found or unable to connect to VastAI service.")
            return
        
        # Display instance status summary
        status_counts = {}
        for instance in instances:
            # Use 'unknown' as default and ensure status is never None
            status = instance.get("status", "unknown")
            if status is None:
                status = "unknown"
                
            if status in status_counts:
                status_counts[status] += 1
            else:
                status_counts[status] = 1
        
        # Show status counts in columns
        st.write("### Instance Status Summary")
        cols = st.columns(len(status_counts) if status_counts else 1)
        
        for i, (status, count) in enumerate(status_counts.items()):
            with cols[i]:
                status_label = status.capitalize() if status is not None else "Unknown"
                st.metric(f"{status_label}", count)
        
        # Create a table of instances
        st.write("### Available Instances")
        
        if instances:
            # Convert to DataFrame for better display
            instance_data = []
            for instance in instances:
                # Ensure we handle all potential None values
                instance_data.append({
                    "Instance ID": instance.get("instance_id", "Unknown") or "Unknown",
                    "Status": instance.get("status", "Unknown") or "Unknown",
                    "GPU": instance.get("gpu_name", "Unknown") or "Unknown",
                    "Machine ID": instance.get("machine_id", "Unknown") or "Unknown"
                })
            
            df = pd.DataFrame(instance_data)
            st.dataframe(df, use_container_width=True)
            
            # Show instance selector
            instance_options = [str(instance.get("instance_id", "Unknown")) for instance in instances]
            selected_instance_id = st.selectbox("Select an instance for details", ["None"] + instance_options)
            
            # Display details of the selected instance if an instance is selected
            if selected_instance_id != "None":
                st.markdown("---")
                
                # Use a more prominent progress indicator with a timeout message
                with st.spinner(f"Fetching details for instance {selected_instance_id}... (This may take up to a minute)"):
                    instance_details = await self.get_vastai_instance_info(selected_instance_id)
                
                if instance_details:
                    st.write(f"### Details for Instance {selected_instance_id}")
                    
                    # Create two columns for instance details
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        uptime = instance_details.get("uptime_hours")
                        uptime_display = str(uptime) if uptime is not None else "N/A"
                        st.metric("Uptime (hours)", uptime_display)
                        
                        total_cost = instance_details.get("total_cost")
                        cost_display = f"${total_cost}" if total_cost is not None else "N/A"
                        st.metric("Total Cost", cost_display)
                        
                        hourly_rate = instance_details.get("hourly_rate")
                        rate_display = f"${hourly_rate}/hour" if hourly_rate is not None else "N/A"
                        st.metric("Hourly Rate", rate_display)
                    
                    with col2:
                        status = instance_details.get("status")
                        status_display = status if status is not None else "N/A"
                        st.metric("Status", status_display)
                        
                        gpu_info = instance_details.get("gpu_info")
                        gpu_display = gpu_info if gpu_info is not None else "N/A"
                        st.metric("GPU", gpu_display)
                        
                        machine_id = instance_details.get("machine_id")
                        machine_display = machine_id if machine_id is not None else "N/A"
                        st.metric("Machine ID", machine_display)
                    
                    # Show logs in expandable section
                    with st.expander("Instance Logs", expanded=True):
                        logs = instance_details.get("logs")
                        log_content = logs if logs is not None else "No logs available"
                        st.text_area("Log Output", log_content, height=300, disabled=True)
                        
                    # Add refresh button for this specific instance
                    if st.button("🔄 Refresh Instance Details"):
                        st.experimental_rerun()
                else:
                    st.error(f"Unable to fetch details for instance {selected_instance_id}")
        else:
            st.info("No instances available")
            
        # Add a refresh button
        if st.button("🔄 Refresh All Instances"):
            st.experimental_rerun()
    
    def run(self):
        """Main entry point for the Streamlit app."""
        if not st.session_state.authenticated:
            self.login_page()
        else:
            self.main_dashboard()


class HTTP_SERVER():
    def __init__(self, httpServerHost, httpServerPort, httpServerPrivilegedIpAddress=["127.0.0.1"], data_class_instance=None):
        self.app = FastAPI()
        self.host = httpServerHost
        self.port = httpServerPort

        self.privilegedIpAddress = httpServerPrivilegedIpAddress        #<HTTP_SERVER_CORS_ADDITION_START>
        self.app.add_middleware(CORSMiddleware, allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"],)
        #<HTTP_SERVER_CORS_ADDITION_END>
        
        self.data_class = data_class_instance  # Reference to the Data class instance
        
        # Get MongoDB service URL from environment
        env_url = os.getenv("MONGODB_SERVICE", "").strip()
        if not env_url or not (env_url.startswith("http://") or env_url.startswith("https://")):
            self.mongodb_service_url = "http://127.0.0.1:12000"
        else:
            self.mongodb_service_url = env_url
        
        # Get Auth service URL from environment
        auth_env_url = os.getenv("AUTH_SERVICE", "").strip()
        if not auth_env_url or not (auth_env_url.startswith("http://") or auth_env_url.startswith("https://")):
            self.auth_service_url = "http://127.0.0.1:10000"
        else:
            self.auth_service_url = auth_env_url
        
        # Get Blob service URL from environment
        blob_env_url = os.getenv("BLOB_SERVICE", "").strip()
        if not blob_env_url or not (blob_env_url.startswith("http://") or blob_env_url.startswith("https://")):
            self.blob_service_url = "http://127.0.0.1:13000"
        else:
            self.blob_service_url = blob_env_url
        
        self.blob_storage_base_url = "http://localhost:9000"
        
        # Get Session Supervisor service URL from environment
        session_supervisor_env_url = os.getenv("SESSION_SUPERVISOR_SERVICE", "").strip()
        if not session_supervisor_env_url or not (session_supervisor_env_url.startswith("http://") or session_supervisor_env_url.startswith("https://")):
            self.session_supervisor_service_url = "http://127.0.0.1:7500"
        else:
            self.session_supervisor_service_url = session_supervisor_env_url
        
        # Get User Manager service URL from environment
        user_manager_env_url = os.getenv("USER_MANAGER_SERVICE", "").strip()
        if not user_manager_env_url or not (user_manager_env_url.startswith("http://") or user_manager_env_url.startswith("https://")):
            self.user_manager_service_url = "http://127.0.0.1:7000"
        else:
            self.user_manager_service_url = user_manager_env_url
        
        # HTTP client for making requests to MongoDB service and Auth service
        self.http_client = httpx.AsyncClient(timeout=30.0)


    # ----------------------------
    # API Calls Section
    # ----------------------------

    async def configure_routes(self):

        # @self.app.post("/api/customer-service/test-auth")
        # async def testAuth(
        #     request: Request, 
        #     access_token: str = Depends(self.authenticate_token)
        # ):
        #     print(f"Test Auth endpoint hit for customer: {access_token}")
        #     return JSONResponse(content={
        #         "message": "Authentication successful", 
        #         "customer_id": access_token,
        #         "status": "authorized",
        #         "timestamp": datetime.now().isoformat()
        #     }, status_code=200)
        
        @self.app.post("/api/admin-panel-service/")
        async def adminPanelServiceRoot(request: Request):
            """
            Admin Panel Service Health Check Endpoint
            
            This endpoint provides a simple health check to verify that the Admin Panel Service
            is running and accessible.
            
            Returns:
                JSONResponse: A simple status message confirming the service is active
                
            Example Response:
                {
                    "message": "Admin Panel Service is active"
                }
            """
            print("Admin Panel Service Root Endpoint Hit")
            return JSONResponse(content={"message": "Admin Panel Service is active"}, status_code=200)
         

        # ----------------------------
        # Session Supervisor API Calls
        # ----------------------------

        @self.app.get("/api/admin-panel-service/get-all-session-supervisor-information")
        async def getAllSessionSupervisorInformation(request: Request):
            """
            Get information about all active session supervisors.
            
            This endpoint retrieves comprehensive information about all active
            session supervisors from the Session Supervisor Service. It provides
            an overview of all running rendering sessions, their status, and
            associated metadata.
            
            Args:
                request (Request): FastAPI request object
                
            Returns:
                JSONResponse: Response containing list of all session supervisor information
                
            Status Codes:
                200: Information retrieved successfully
                500: Error communicating with Session Supervisor Service
                
            Example Response:
                [
                    {
                        "object_id": "object-123",
                        "session_routing_key": "SESSION_SUPERVISOR_abc-123",
                        "session_id": "session-456",
                        "number_of_users": 3,
                        "session_status": "running"
                    },
                    {
                        "object_id": "object-789",
                        "session_routing_key": "SESSION_SUPERVISOR_def-456",
                        "session_id": "session-789",
                        "number_of_users": 2,
                        "session_status": "completed"
                    }
                ]
            """
            try:
                response = await self.http_client.get(
                    f"{self.session_supervisor_service_url}/api/session-supervisor-service/get-all-supervisor-information"
                )
                
                if response.status_code == 200:
                    return JSONResponse(content=response.json(), status_code=200)
                else:
                    return JSONResponse(
                        content={"message": "Failed to retrieve session supervisor information"}, 
                        status_code=response.status_code
                    )
            except Exception as e:
                return JSONResponse(
                    content={"message": f"Error communicating with Session Supervisor Service: {str(e)}"}, 
                    status_code=500
                )
    
        @self.app.get("/api/admin-panel-service/get-session-supervisor-overview/{customer_id}")
        async def getSessionSupervisorOverview(customer_id: str):
            """
            Get detailed overview information for a specific session supervisor.
            
            This endpoint retrieves comprehensive information about a specific
            session supervisor identified by customer_id. It provides details
            about the session status, user assignments, and other session metadata.
            
            Args:
                customer_id (str): Unique identifier for the customer/session supervisor
                                 Provided as path parameter
                
            Returns:
                JSONResponse: Response containing session supervisor overview information
                
            Status Codes:
                200: Overview retrieved successfully
                404: No active session found for customer
                500: Error communicating with Session Supervisor Service
                
            Example Response:
                {
                    "object_id": "object-123",
                    "session_routing_key": "SESSION_SUPERVISOR_abc-123",
                    "session_id": "session-456",
                    "number_of_users": 3,
                    "session_status": "running"
                }
            """
            try:
                response = await self.http_client.get(
                    f"{self.session_supervisor_service_url}/api/session-supervisor-service/get-session-supervisor-overview/{customer_id}"
                )
                
                if response.status_code == 200:
                    return JSONResponse(content=response.json(), status_code=200)
                else:
                    return JSONResponse(
                        content={"message": f"Failed to retrieve session supervisor overview for customer_id: {customer_id}"}, 
                        status_code=response.status_code
                    )
            except Exception as e:
                return JSONResponse(
                    content={"message": f"Error communicating with Session Supervisor Service: {str(e)}"}, 
                    status_code=500
                )
    
        @self.app.get("/api/admin-panel-service/get-session-supervisor-user-count/{customer_id}")
        async def getSessionSupervisorUserCount(customer_id: str):
            """
            Get the current number of users assigned to a session supervisor.
            
            This endpoint retrieves the current user count for a specific session
            supervisor identified by customer_id. It provides information about
            how many users are currently assigned to handle the rendering workload.
            
            Args:
                customer_id (str): Unique identifier for the customer/session supervisor
                                 Provided as path parameter
                
            Returns:
                JSONResponse: Response containing user count information
                
            Status Codes:
                200: User count retrieved successfully
                404: No active session found for customer
                500: Error communicating with Session Supervisor Service
                
            Example Response:
                {
                    "customer_id": "customer-123",
                    "user_count": 3,
                    "message": "User count retrieved successfully"
                }
            """
            try:
                response = await self.http_client.get(
                    f"{self.session_supervisor_service_url}/api/session-supervisor-service/get-user-count/{customer_id}"
                )
                
                if response.status_code == 200:
                    return JSONResponse(content=response.json(), status_code=200)
                else:
                    return JSONResponse(
                        content={"message": f"Failed to retrieve user count for customer_id: {customer_id}"}, 
                        status_code=response.status_code
                    )
            except Exception as e:
                return JSONResponse(
                    content={"message": f"Error communicating with Session Supervisor Service: {str(e)}"}, 
                    status_code=500
                )
    
        @self.app.put("/api/admin-panel-service/set-session-supervisor-user-count/{customer_id}/{user_count}")
        async def setSessionSupervisorUserCount(customer_id: str, user_count: int):
            """
            Set the number of users assigned to a session supervisor.
            
            This endpoint allows administrators to dynamically adjust the number
            of users assigned to a specific session supervisor. This can be used
            to scale up or down the rendering capacity based on workload demands
            or system resources.
            
            Args:
                customer_id (str): Unique identifier for the customer/session supervisor
                                 Provided as path parameter
                user_count (int): Desired number of users to assign
                                Provided as path parameter
                
            Returns:
                JSONResponse: Response containing the result of the user count update
                
            Status Codes:
                200: User count updated successfully
                404: No active session found for customer
                500: Error communicating with Session Supervisor Service
                
            Example Response:
                {
                    "customer_id": "customer-123",
                    "user_count": 5,
                    "message": "User count updated successfully"
                }
            """
            try:
                response = await self.http_client.post(
                    f"{self.session_supervisor_service_url}/api/session-supervisor-service/set-user-count/{customer_id}/{user_count}"
                )
                
                if response.status_code == 200:
                    return JSONResponse(content=response.json(), status_code=200)
                else:
                    return JSONResponse(
                        content={"message": f"Failed to set user count for customer_id: {customer_id}"}, 
                        status_code=response.status_code
                    )
            except Exception as e:
                return JSONResponse(
                    content={"message": f"Error communicating with Session Supervisor Service: {str(e)}"}, 
                    status_code=500
                )

        # ----------------------------
        # User Manager API Calls
        # ----------------------------

        @self.app.get("/api/admin-panel-service/get-user-manager-overview")
        async def getUserManagerOverview(request: Request):
            """
            Get comprehensive overview of User Manager service state.
            
            This endpoint retrieves detailed information about the current state
            of the User Manager service, including user mappings, session
            supervisor information, demand queue status, and active sessions.
            
            Args:
                request (Request): FastAPI request object
                
            Returns:
                JSONResponse: Response containing User Manager overview information
                
            Status Codes:
                200: Overview retrieved successfully
                500: Error communicating with User Manager Service
                
            Example Response:
                {
                    "userToSupervisorIdMapping": {
                        "user-123": "supervisor-456",
                        "user-789": "supervisor-456"
                    },
                    "supervisorToRoutingKeyMapping": {
                        "supervisor-456": "SESSION_SUPERVISOR_456"
                    },
                    "user_demand_queue": [
                        {
                            "user_count": 3,
                            "session_supervisor_id": "supervisor-789"
                        }
                    ],
                    "activeSessions": ["supervisor-456", "supervisor-789"],
                    "idle_users": ["user-111", "user-222"]
                }
            """
            try:
                response = await self.http_client.get(
                    f"{self.user_manager_service_url}/api/user-manager/get-overview"
                )
                
                if response.status_code == 200:
                    return JSONResponse(content=response.json(), status_code=200)
                else:
                    return JSONResponse(
                        content={"message": "Failed to retrieve User Manager overview"}, 
                        status_code=response.status_code
                    )
            except Exception as e:
                return JSONResponse(
                    content={"message": f"Error communicating with User Manager Service: {str(e)}"}, 
                    status_code=500
                )

        # ----------------------------
        # System Overview API Calls
        # ----------------------------

        @self.app.get("/api/admin-panel-service/get-system-overview")
        async def getSystemOverview(request: Request):
            """
            Get comprehensive system overview combining all services.
            
            This endpoint provides a complete overview of the entire system by
            combining information from both the User Manager and Session Supervisor
            services. It gives administrators a unified view of the system state.
            
            Args:
                request (Request): FastAPI request object
                
            Returns:
                JSONResponse: Response containing comprehensive system overview
                
            Status Codes:
                200: System overview retrieved successfully
                500: Error communicating with services
                
            Example Response:
                {
                    "user_manager": {
                        "userToSupervisorIdMapping": {...},
                        "supervisorToRoutingKeyMapping": {...},
                        "user_demand_queue": [...],
                        "activeSessions": [...],
                        "idle_users": [...]
                    },
                    "session_supervisors": [
                        {
                            "object_id": "object-123",
                            "session_routing_key": "SESSION_SUPERVISOR_abc-123",
                            "session_id": "session-456",
                            "number_of_users": 3,
                            "session_status": "running"
                        }
                    ],
                    "system_summary": {
                        "total_active_sessions": 2,
                        "total_idle_users": 5,
                        "total_demand_requests": 1
                    }
                }
            """
            try:
                # Get User Manager overview
                user_manager_response = await self.http_client.get(
                    f"{self.user_manager_service_url}/api/user-manager/get-overview"
                )
                
                # Get Session Supervisor information
                session_supervisor_response = await self.http_client.get(
                    f"{self.session_supervisor_service_url}/api/session-supervisor-service/get-all-supervisor-information"
                )
                
                user_manager_data = user_manager_response.json() if user_manager_response.status_code == 200 else {}
                session_supervisor_data = session_supervisor_response.json() if session_supervisor_response.status_code == 200 else []
                
                # Calculate system summary
                system_summary = {
                    "total_active_sessions": len(user_manager_data.get("activeSessions", [])),
                    "total_idle_users": len(user_manager_data.get("idle_users", [])),
                    "total_demand_requests": len(user_manager_data.get("user_demand_queue", [])),
                    "total_session_supervisors": len(session_supervisor_data)
                }
                
                system_overview = {
                    "user_manager": user_manager_data,
                    "session_supervisors": session_supervisor_data,
                    "system_summary": system_summary
                }
                
                return JSONResponse(content=system_overview, status_code=200)
                
            except Exception as e:
                return JSONResponse(
                    content={"message": f"Error retrieving system overview: {str(e)}"}, 
                    status_code=500
                )

    async def run_app(self):
        config = uvicorn.Config(self.app, host=self.host, port=self.port)
        server = uvicorn.Server(config)
        await server.serve()

class Data():
    def __init__(self):
        pass

class Service():
    def __init__(self, httpServer = None):
        self.httpServer = httpServer

    async def startService(self):
        await self.httpServer.configure_routes()
        await self.httpServer.run_app()

        
async def start_service():
    """Start the HTTP API service."""
    dataClass = Data()

    #<HTTP_SERVER_INSTANCE_INTIALIZATION_START>

    #<HTTP_SERVER_PORT_START>
    httpServerPort = 15000
    #<HTTP_SERVER_PORT_END>

    #<HTTP_SERVER_HOST_START>
    httpServerHost = "0.0.0.0"
    #<HTTP_SERVER_HOST_END>

    #<HTTP_SERVER_PRIVILEGED_IP_ADDRESS_START>
    httpServerPrivilegedIpAddress = ["127.0.0.1"]
    #<HTTP_SERVER_PRIVILEGED_IP_ADDRESS_END>

    http_server = HTTP_SERVER(httpServerHost=httpServerHost, httpServerPort=httpServerPort, httpServerPrivilegedIpAddress=httpServerPrivilegedIpAddress, data_class_instance=dataClass)
    #<HTTP_SERVER_INSTANCE_INTIALIZATION_END>

    service = Service(http_server)
    await service.startService()

def start_streamlit_app():
    """Start the Streamlit admin panel."""
    admin_panel = AdminPanelStreamlit()
    admin_panel.run()

# Streamlit app entry point
def main():
    """Main Streamlit application entry point."""
    admin_panel = AdminPanelStreamlit()
    admin_panel.run()

# Check if running with streamlit run command
if __name__ == "__main__":
    import sys
    
    # If streamlit is in the modules, we're running with 'streamlit run'
    if "streamlit" in sys.modules:
        main()
    elif len(sys.argv) > 1 and sys.argv[1] == "streamlit":
        # Run Streamlit interface via function call
        start_streamlit_app()
    elif len(sys.argv) > 1 and sys.argv[1] == "api":
        # Run HTTP API service explicitly
        asyncio.run(start_service())
    else:
        # Default: Show instructions for running Streamlit
        print("=" * 60)
        print("🔧 Admin Panel Service")
        print("=" * 60)
        print("To run the Streamlit Admin Panel:")
        print("  streamlit run admin-panel-service.py --server.port 15000")
        print()
        print("To run the HTTP API Service:")
        print("  python admin-panel-service.py api")
        print()
        print("Default credentials: admin / password")
        print("=" * 60)