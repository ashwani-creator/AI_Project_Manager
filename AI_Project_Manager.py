import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime
from pathlib import Path

st.set_page_config(page_title="Project Manager", page_icon="📋", layout="wide")
DB_PATH = Path(__file__).with_name("project_manager.db")

# ---------- Database ----------
def db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, group_name TEXT, student_name TEXT,
            faculty_name TEXT, start_date TEXT, deadline TEXT, description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        con.execute("""CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL, title TEXT NOT NULL, status TEXT DEFAULT 'Pending',
            due_date TEXT, priority TEXT DEFAULT 'Medium',
            FOREIGN KEY(project_id) REFERENCES projects(id))""")

def query(sql, params=()):
    with db() as con:
        return pd.read_sql_query(sql, con, params=params)

def execute(sql, params=()):
    with db() as con:
        cur = con.execute(sql, params)
        con.commit()
        return cur.lastrowid

init_db()

# ---------- Helpers ----------
def project_stats(pid):
    tasks = query("SELECT * FROM tasks WHERE project_id=?", (pid,))
    total = len(tasks)
    done = int((tasks.status == "Completed").sum()) if total else 0
    progress = round(done / total * 100) if total else 0
    return tasks, total, done, progress

def watcher(project, tasks, progress):
    """Simple rules-based status; not a trained AI prediction model."""
    today = date.today()
    try:
        deadline = date.fromisoformat(project["deadline"])
    except Exception:
        deadline = None
    overdue_tasks = 0
    if len(tasks):
        for _, task in tasks.iterrows():
            if task["status"] != "Completed" and task["due_date"]:
                try:
                    if date.fromisoformat(task["due_date"]) < today:
                        overdue_tasks += 1
                except Exception:
                    pass
    if overdue_tasks or (deadline and deadline < today and progress < 100):
        return "Delayed", "Some deadlines have passed. Review pending tasks and update the plan."
    if deadline and (deadline - today).days <= 7 and progress < 70:
        return "Needs Attention", "The project deadline is close. Prioritize the remaining work."
    if progress == 0 and deadline and (deadline - today).days <= 14:
        return "Needs Attention", "No tasks are marked complete yet. Start with the smallest task."
    return "On Track", "Current task status does not show an overdue warning. Keep updates regular."


def status_badge(status):
    color = {"On Track": "🟢", "Needs Attention": "🟡", "Delayed": "🔴"}.get(status, "⚪")
    return f"{color} **{status}**"

# ---------- Styling ----------
st.markdown("""<style>
.block-container {padding-top: 1.6rem; padding-bottom: 2rem; max-width: 1200px;}
[data-testid="stMetric"] {background: #f6f8fb; padding: 14px 16px; border-radius: 10px; border: 1px solid #e8edf3;}
[data-testid="stMetricLabel"] {color: #4b5563;}
div.stButton > button {border-radius: 8px;}
</style>""", unsafe_allow_html=True)


# ---------- Sidebar navigation ----------
st.sidebar.title("📋 Project Manager")
st.sidebar.caption("Student project workspace")
page = st.sidebar.radio("Navigation", ["Dashboard", "My Projects", "Tasks", "Faculty Monitor", "Reports", "About"])
st.sidebar.divider()
st.sidebar.caption("A simple project tracking and monitoring tool")

projects = query("SELECT * FROM projects ORDER BY id DESC")
all_tasks = query("SELECT * FROM tasks")

# ---------- Dashboard ----------
if page == "Dashboard":
    st.title("Dashboard")
    st.write("A quick overview of your projects and tasks.")
    total_projects = len(projects)
    task_count = len(all_tasks)
    completed_count = int((all_tasks.status == "Completed").sum()) if task_count else 0
    pending_count = task_count - completed_count
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Projects", total_projects)
    c2.metric("Total Tasks", task_count)
    c3.metric("Completed", completed_count)
    c4.metric("Pending", pending_count)

    st.subheader("Project overview")
    if projects.empty:
        st.info("No projects have been added yet. Open My Projects to create your first project.")
    else:
        overview = []
        for _, p in projects.iterrows():
            t, total, done, prog = project_stats(int(p.id))
            try:
                remaining = (date.fromisoformat(p.deadline) - date.today()).days if p.deadline else None
            except Exception:
                remaining = None
            overview.append({"Project": p.name, "Group": p.group_name or "—", "Progress": f"{prog}%", "Tasks": f"{done}/{total}", "Days left": remaining if remaining is not None else "—", "Deadline": p.deadline or "—"})
        st.dataframe(pd.DataFrame(overview), use_container_width=True, hide_index=True)
        st.subheader("Recent tasks")
        recent = query("""SELECT tasks.title AS Task, projects.name AS Project, tasks.status AS Status,
                       tasks.due_date AS Due, tasks.priority AS Priority
                       FROM tasks JOIN projects ON tasks.project_id=projects.id
                       ORDER BY tasks.id DESC LIMIT 8""")
        if recent.empty:
            st.caption("Tasks you add will appear here.")
        else:
            st.dataframe(recent, use_container_width=True, hide_index=True)

# ---------- Projects ----------
elif page == "My Projects":
    st.title("My Projects")
    with st.expander("＋ Create a project", expanded=projects.empty):
        with st.form("new_project", clear_on_submit=True):
            name = st.text_input("Project name *")
            group = st.text_input("Group / team name")
            student = st.text_input("Student name / team members")
            faculty = st.text_input("Faculty mentor")
            col1, col2 = st.columns(2)
            start = col1.date_input("Start date", value=date.today())
            deadline = col2.date_input("Deadline", value=date.today())
            description = st.text_area("Short description")
            create = st.form_submit_button("Save project", type="primary")
            if create:
                if not name.strip():
                    st.error("Please enter a project name.")
                elif deadline < start:
                    st.error("Deadline cannot be before start date.")
                else:
                    execute("INSERT INTO projects(name,group_name,student_name,faculty_name,start_date,deadline,description) VALUES(?,?,?,?,?,?,?)",
                            (name.strip(), group, student, faculty, start.isoformat(), deadline.isoformat(), description))
                    st.success("Project saved.")
                    st.rerun()
    projects = query("SELECT * FROM projects ORDER BY id DESC")
    if projects.empty:
        st.info("Your saved projects will appear here.")
    else:
        for _, p in projects.iterrows():
            with st.container(border=True):
                st.markdown(f"### {p['name']}")
                if p["description"]:
                    st.write(p["description"])
                st.caption(f"Team: {p['group_name'] or '—'}  |  Faculty: {p['faculty_name'] or '—'}  |  Deadline: {p['deadline'] or '—'}")
                t, total, done, progress = project_stats(int(p.id))
                st.progress(progress / 100, text=f"Progress: {progress}% ({done} of {total} tasks completed)")
                col_a, col_b = st.columns([4, 1])
                col_a.write(status_badge(watcher(p, t, progress)[0]))
                if col_b.button("Delete project", key=f"delproj{p.id}"):
                    execute("DELETE FROM tasks WHERE project_id=?", (int(p.id),))
                    execute("DELETE FROM projects WHERE id=?", (int(p.id),))
                    st.rerun()

# ---------- Tasks ----------
elif page == "Tasks":
    st.title("Tasks")
    projects = query("SELECT * FROM projects ORDER BY name")
    if projects.empty:
        st.warning("Create a project first in My Projects.")
    else:
        project_map = {f"{row['name']} (ID {row['id']})": int(row["id"]) for _, row in projects.iterrows()}
        chosen = st.selectbox("Choose project", list(project_map.keys()))
        pid = project_map[chosen]
        with st.expander("＋ Add a task", expanded=False):
            with st.form("new_task", clear_on_submit=True):
                title = st.text_input("Task name *")
                due = st.date_input("Task due date", value=date.today(), key="task_due")
                priority = st.selectbox("Priority", ["Low", "Medium", "High"], index=1)
                add = st.form_submit_button("Add task")
                if add:
                    if not title.strip():
                        st.error("Please enter a task name.")
                    else:
                        execute("INSERT INTO tasks(project_id,title,status,due_date,priority) VALUES(?,?, 'Pending',?,?)", (pid, title.strip(), due.isoformat(), priority))
                        st.success("Task added")
                        st.rerun()
        tasks = query("SELECT * FROM tasks WHERE project_id=? ORDER BY id DESC", (pid,))
        if tasks.empty:
            st.info("No tasks yet. Add your first task above.")
        else:
            st.subheader("Task checklist")
            for _, task in tasks.iterrows():
                cols = st.columns([0.5, 4, 1.3, 1, 1])
                checked = task.status == "Completed"
                new_checked = cols[0].checkbox("", value=checked, key=f"check{task.id}", label_visibility="collapsed")
                cols[1].markdown(("~~" + task.title + "~~") if new_checked else f"**{task.title}**")
                cols[2].caption(task.due_date or "No date")
                cols[3].caption(task.priority)
                cols[4].button("Delete", key=f"del{task.id}", on_click=lambda tid=int(task.id): execute("DELETE FROM tasks WHERE id=?", (tid,)))
                if new_checked != checked:
                    execute("UPDATE tasks SET status=? WHERE id=?", ("Completed" if new_checked else "Pending", int(task.id)))
                    st.rerun()
            _, total, done, prog = project_stats(pid)
            st.progress(prog / 100, text=f"Project completion: {prog}%")

# ---------- Faculty Monitor ----------
elif page == "Faculty Monitor":
    st.title("Faculty Monitor")
    st.caption("Project status is based on task completion and deadline rules. It is an indicator, not a performance grade.")
    projects = query("SELECT * FROM projects ORDER BY deadline")
    if projects.empty:
        st.info("No projects to monitor yet.")
    else:
        for _, p in projects.iterrows():
            tasks, total, done, progress = project_stats(int(p.id))
            status, note = watcher(p, tasks, progress)
            with st.container(border=True):
                st.markdown(f"### {p.name}")
                st.write(f"**Group:** {p.group_name or '—'} | **Student(s):** {p.student_name or '—'} | **Faculty:** {p.faculty_name or '—'}")
                st.write(f"**Deadline:** {p.deadline or '—'}")
                st.progress(progress / 100, text=f"{progress}% complete ({done}/{total} tasks)")
                st.markdown(status_badge(status))
                st.caption(note)
                pending = tasks[tasks.status != "Completed"] if len(tasks) else tasks
                if len(pending):
                    st.write("**Pending tasks:** " + ", ".join(pending.title.astype(str).tolist()))
                else:
                    st.write("No pending tasks recorded.")

# ---------- Reports ----------
elif page == "Reports":
    st.title("Reports")
    projects = query("SELECT * FROM projects ORDER BY name")
    if projects.empty:
        st.info("Add projects to create a report.")
    else:
        rows = []
        for _, p in projects.iterrows():
            tasks, total, done, prog = project_stats(int(p.id))
            status, note = watcher(p, tasks, prog)
            rows.append({"Project": p.name, "Group": p.group_name or "", "Deadline": p.deadline or "", "Total Tasks": total, "Completed": done, "Pending": total-done, "Progress %": prog, "Status": status})
        report = pd.DataFrame(rows)
        st.dataframe(report, use_container_width=True, hide_index=True)
        st.download_button("Download CSV report", report.to_csv(index=False).encode("utf-8"), file_name="project_report.csv", mime="text/csv")

# ---------- About ----------
elif page == "About":
    st.title("About this application")
    st.write("Project Manager is a small project-tracking application made with Python and Streamlit. It helps students record projects, break work into tasks, update completion status, and lets faculty view a basic project summary.")
    st.subheader("How the project status works")
    st.write("The current watcher uses simple deadline and task-status rules. It is not a trained machine-learning model. A future version could use historical project data to evaluate risk more carefully.")
    st.subheader("Technology used")
    st.write("Python · Streamlit · SQLite · Pandas")
    st.caption("SQLite stores the data in a local database file beside this app. On Streamlit Cloud, local files may not persist across some redeployments or restarts; use a hosted database for dependable long-term storage.")

st.sidebar.caption("Built for student project tracking")
