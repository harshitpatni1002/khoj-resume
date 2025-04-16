import streamlit as st
import nltk
import spacy
import pandas as pd
import base64
import random
import time
import datetime
import os
import pymysql
from pyresparser import ResumeParser
from pdfminer3.layout import LAParams, LTTextBox
from pdfminer3.pdfpage import PDFPage
from pdfminer3.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer3.converter import TextConverter
import io
from streamlit_tags import st_tags
from PIL import Image
import pafy
import plotly.express as px
import youtube_dl

# Download necessary NLTK data
nltk.download('stopwords')

# Load Spacy model
spacy.load('en_core_web_sm')

# Import courses module
from Courses import ds_course, web_course, android_course, ios_course, uiux_course, resume_videos, interview_videos

# Database Connection
connection = pymysql.connect(host='localhost', user='root', password='root')
cursor = connection.cursor()

# Utility Functions
def fetch_yt_video(link):
    video = pafy.new(link)
    return video.title

def get_table_download_link(df, filename, text):
    """Generates a link allowing the data in a given pandas dataframe to be downloaded."""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()  # encode dataframe to CSV
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">{text}</a>'

def pdf_reader(file):
    """Extracts text from PDF file using pdfminer."""
    resource_manager = PDFResourceManager()
    fake_file_handle = io.StringIO()
    converter = TextConverter(resource_manager, fake_file_handle, laparams=LAParams())
    page_interpreter = PDFPageInterpreter(resource_manager, converter)
    
    with open(file, 'rb') as fh:
        for page in PDFPage.get_pages(fh, caching=True, check_extractable=True):
            page_interpreter.process_page(page)
        text = fake_file_handle.getvalue()

    converter.close()
    fake_file_handle.close()
    return text

def show_pdf(file_path):
    """Displays PDF in Streamlit app."""
    with open(file_path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
    pdf_display = F'<iframe src="data:application/pdf;base64,{base64_pdf}" width="700" height="1000" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

# Resume Parsing and Analysis
def analyze_resume(file):
    """Analyze the resume and return the extracted data."""
    save_image_path = './Uploaded_Resumes/' + file.name
    os.makedirs(os.path.dirname(save_image_path), exist_ok=True)

    with open(save_image_path, "wb") as f:
        f.write(file.getbuffer())

    show_pdf(save_image_path)
    return ResumeParser(save_image_path).get_extracted_data(), save_image_path

# Course Recommendations
def course_recommender(course_list):
    st.subheader("**Courses & Certificates🎓 Recommendations**")
    rec_course = []
    no_of_reco = st.slider('Choose Number of Course Recommendations:', 1, 10, 4)
    random.shuffle(course_list)
    for c, (c_name, c_link) in enumerate(course_list):
        if c == no_of_reco:
            break
        st.markdown(f"({c+1}) [{c_name}]({c_link})")
        rec_course.append(c_name)
    return rec_course

# Insert Data into Database
def insert_data(name, email, resume_score, timestamp, no_of_pages, reco_field, cand_level, actual_skills, recommended_skills, rec_course):
    # Define maximum length for each column
    max_skills_length = 1000

    # Truncate data if necessary
    actual_skills = actual_skills[:max_skills_length]
    recommended_skills = recommended_skills[:max_skills_length]  # If needed
    rec_course = rec_course[:max_skills_length]  # If needed

    insert_sql = """INSERT INTO resume_data (name, email, resume_score, timestamp, no_of_pages, reco_field, cand_level, Actual_skills, Recommended_skills, Recommended_courses)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
    
    # Values to be inserted
    rec_values = (name, email, resume_score, timestamp, no_of_pages, reco_field, cand_level, actual_skills, recommended_skills, rec_course)

    # Execute the query

    cursor.execute(insert_sql, rec_values)
    connection.commit()


# Main function to run the app
def run():
    st.set_page_config(page_title="Smart Resume Analyzer", page_icon='./Logo/SRA_Logo.ico')
    st.title("Smart Resume Analyser")
    
    # Sidebar and navigation
    st.sidebar.markdown("# Choose User")
    activities = ["Normal User", "Admin"]
    choice = st.sidebar.selectbox("Choose among the given options:", activities)
    
    # Logo and branding
    img = Image.open('./Logo/SRA_Logo.jpg')
    img = img.resize((250, 250))
    st.image(img)
    
    # DB Setup
    cursor.execute("CREATE DATABASE IF NOT EXISTS SRA;")
    connection.select_db("sra")
    create_user_table()

    if choice == 'Normal User':
        handle_normal_user()
    else:
        handle_admin()

def create_user_table():
    """Create table for storing user data if not exists."""
    table_sql = """
        CREATE TABLE IF NOT EXISTS user_data (
            ID INT NOT NULL AUTO_INCREMENT,
            Name varchar(100) NOT NULL,
            Email_ID VARCHAR(50) NOT NULL,
            resume_score VARCHAR(8) NOT NULL,
            Timestamp VARCHAR(50) NOT NULL,
            Page_no VARCHAR(5) NOT NULL,
            Predicted_Field VARCHAR(25) NOT NULL,
            User_level VARCHAR(30) NOT NULL,
            Actual_skills VARCHAR(300) NOT NULL,
            Recommended_skills VARCHAR(300) NOT NULL,
            Recommended_courses VARCHAR(600) NOT NULL,
            PRIMARY KEY (ID)
        );
    """
    cursor.execute(table_sql)

def handle_normal_user():
    """Handle normal user flow: Upload resume and analyze it."""
    pdf_file = st.file_uploader("Choose your Resume", type=["pdf"])

    if pdf_file:
        resume_data, save_image_path = analyze_resume(pdf_file)
        
        if resume_data:
            st.success(f"Hello {resume_data.get('name')}")
            display_basic_info(resume_data)

            # Calculate resume score
            resume_score = calculate_resume_score(save_image_path)  # Calculate score based on resume content
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Define candidate's level based on experience or other factors
            # Here we assume you can extract years of experience from the resume or manually assign it
            experience = resume_data.get('experience', [])
            if len(experience) == 0:
                cand_level = "Beginner"  # If no experience found
            elif len(experience) <= 3:
                cand_level = "Intermediate"
            else:
                cand_level = "Expert"
            
            # Get the field and recommendations
            reco_field, recommended_skills, rec_course = analyze_skills_and_recommend_courses(resume_data)

            display_resume_score_and_tips(resume_data, save_image_path)
            
            # Insert the data into the database
            insert_data(resume_data['name'], resume_data['email'], resume_score, timestamp, resume_data['no_of_pages'], reco_field, cand_level, str(resume_data['skills']), str(recommended_skills), str(rec_course))

            # Resume and Interview Video Tips
            display_video_tips()

        else:
            st.error('Failed to parse resume.')

def display_basic_info(resume_data):
    """Display basic user information."""
    st.subheader("**Your Basic info**")
    try:
        st.text(f"Name: {resume_data['name']}")
        st.text(f"Email: {resume_data['email']}")
        st.text(f"Contact: {resume_data['mobile_number']}")
        st.text(f"Resume pages: {str(resume_data['no_of_pages'])}")
    except KeyError:
        pass

def analyze_skills_and_recommend_courses(resume_data):
    """Analyze skills and recommend courses."""
    st.subheader("**Skills Recommendation💡**")
    keywords = st_tags(label='### Skills that you have', text='See our skills recommendation', value=resume_data['skills'], key='1')
    
    # Ensure that this function returns reco_field, recommended_skills, and rec_course
    recommended_skills, reco_field, rec_course = analyze_skills(resume_data)
    
    # Display results
    st.success(f"** Recommended skills for {reco_field}: **")
    st_tags(label='### Recommended skills for you.', value=recommended_skills, key='2')
    course_recommender(rec_course)

    return reco_field, recommended_skills, rec_course  # Return the values

def analyze_skills(resume_data):
    """Analyze the skills in the resume and return recommended skills, field, and courses."""
    
    # Example: Analyze skills in the resume
    skills = resume_data.get("skills", [])
    
    # Define recommended skills and courses based on the user's skills
    recommended_skills = []
    reco_field = "Unknown"
    rec_course = []

    if "python" in [s.lower() for s in skills]:
        recommended_skills = ["Machine Learning", "Data Science", "Artificial Intelligence"]
        reco_field = "Data Science"
        rec_course = [("Python for Data Science - Coursera", "https://www.coursera.org/courses?query=python%20for%20data%20science"),
                      ("AI for Everyone - Coursera", "https://www.coursera.org/learn/ai-for-everyone")]
    elif "java" in [s.lower() for s in skills]:
        recommended_skills = ["Java Development", "Spring Framework", "Web Development"]
        reco_field = "Software Development"
        rec_course = [("Java Programming - Udemy", "https://www.udemy.com/course/java-programming/"),
                      ("Spring Framework for Beginners - Udemy", "https://www.udemy.com/course/spring-framework-for-beginners/")]
    elif "web development" in [s.lower() for s in skills]:
        recommended_skills = ["HTML", "CSS", "JavaScript", "React", "Node.js"]
        reco_field = "Web Development"
        rec_course = [("The Web Developer Bootcamp - Udemy", "https://www.udemy.com/course/the-web-developer-bootcamp/"),
                      ("React - Full Course - Codecademy", "https://www.codecademy.com/learn/react-101")]
    
    # You can add more skills and fields as per your needs
    
    return recommended_skills, reco_field, rec_course

def display_resume_score_and_tips(resume_data, resume_text):
    """Display the resume score and provide improvement tips."""
    resume_score = calculate_resume_score(resume_text)
    st.subheader("**Resume Tips & Ideas💡**")
    st.success(f"** Your Resume Writing Score: {resume_score} **")
    st.warning("** Note: This score is based on the content of your resume. **")
    st.progress(resume_score)

def calculate_resume_score(resume_text):
    """Calculate resume score based on the content."""
    score = 0
    tips = [("Objective", 20), ("Declaration", 20), ("Hobbies", 20), ("Achievements", 20), ("Projects", 20)]
    for section, points in tips:
        if section in resume_text:
            score += points
            st.markdown(f"** [+] You have added {section}.**")
        else:
            st.markdown(f"** [-] Please add {section} to improve your resume.**")
    return score

def display_video_tips():
    """Display resume writing and interview preparation videos."""
    st.header("**Bonus Video for Resume Writing Tips💡**")
    resume_vid = random.choice(resume_videos)
    res_vid_title = fetch_yt_video(resume_vid)
    st.subheader(f"✅ **{res_vid_title}**")
    st.video(resume_vid)

    st.header("**Bonus Video for Interview👨‍💼 Tips💡**")
    interview_vid = random.choice(interview_videos)
    int_vid_title = fetch_yt_video(interview_vid)
    st.subheader(f"✅ **{int_vid_title}**")
    st.video(interview_vid)

def handle_admin():
    """Admin panel to view and download user data."""
    st.success('Welcome to Admin Side')
    ad_user = st.text_input("Username")
    ad_password = st.text_input("Password", type='password')
    if st.button('Login'):
        if ad_user == 'machine_learning_hub' and ad_password == 'mlhub123':
            st.success("Welcome Admin")
            # Show User Data
            cursor.execute("SELECT * FROM user_data")
            data = cursor.fetchall()
            df = pd.DataFrame(data, columns=['ID', 'Name', 'Email', 'Resume Score', 'Timestamp', 'Total Page', 'Predicted Field', 'User Level', 'Actual Skills', 'Recommended Skills', 'Recommended Course'])
            st.dataframe(df)
            st.markdown(get_table_download_link(df, 'User_Data.csv', 'Download Report'), unsafe_allow_html=True)
            
            # Plot Pie charts
            plot_pie_chart(df)
        else:
            st.error("Wrong ID & Password Provided")

def plot_pie_chart(df):
    """Plot pie charts based on the data."""
    labels = df['Predicted_Field'].unique()
    values = df['Predicted_Field'].value_counts()
    st.subheader("📈 Pie Chart for Predicted Field Recommendations")
    fig = px.pie(df, values=values, names=labels, title='Predicted Field')
    st.plotly_chart(fig)

    labels = df['User_level'].unique()
    values = df['User_level'].value_counts()
    st.subheader("📈 Pie Chart for User Experience Level")
    fig = px.pie(df, values=values, names=labels, title="User Experience Level")
    st.plotly_chart(fig)

# Run the Streamlit app
if __name__ == "__main__":
    run()
