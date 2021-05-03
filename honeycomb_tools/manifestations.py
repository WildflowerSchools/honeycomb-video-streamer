import json
import os


def read_classrooms(root_path):
    index_location = os.path.join(root_path, "index.json")
    if not os.path.exists(index_location):
        os.makedirs(os.path.dirname(index_location), exist_ok=True)
        with open(index_location, 'w') as fp:
            json.dump({"classrooms": []}, fp)
            fp.flush()
    with open(index_location, 'r') as fp:
        doc = json.load(fp)
        return doc.get("classrooms")


def add_classroom(root_path, name, id):
    classrooms = read_classrooms(root_path)
    ids = {classroom.get("id") for classroom in classrooms}
    if id in ids:
        print(f"classroom `{id}` already exists")
        return
    classrooms.append({"name": name, "id": id})
    index_location = os.path.join(root_path, "index.json")
    with open(index_location, 'w') as fp:
        json.dump({"classrooms": classrooms}, fp)
        fp.flush()
        print(f"classroom {id} added")


def read_classroom_index(root_path, classroom_id):
    index_location = os.path.join(root_path, classroom_id, "index.json")
    if not os.path.exists(index_location):
        os.makedirs(os.path.dirname(index_location), exist_ok=True)
        with open(index_location, 'w') as fp:
            json.dump({"dates": []}, fp)
            fp.flush()
    with open(index_location, 'r') as fp:
        doc = json.load(fp)
        return doc.get("dates")


def add_date_to_classroom(root_path, classroom_id, date, name, time_range):
    classroom = read_classroom_index(root_path, classroom_id)
    names = {entry.get("name") for entry in classroom}
    if name in names:
        print(
            f"entry `{name}` already exists in classroom index.json: {names}")
        return
    classroom.append({
        "name": name,
        "url": f"/videos/{classroom_id}/{date}/index.json",
        "date": date,
        "ranges": [
            time_range
        ]
    })
    index_location = os.path.join(root_path, classroom_id, "index.json")
    os.makedirs(os.path.dirname(index_location), exist_ok=True)
    with open(index_location, 'w') as fp:
        json.dump({"dates": classroom}, fp)
        fp.flush()
        print(f"entry {name} added")


if __name__ == '__main__':
    # print(read_classrooms("./public/videos"))
    # add_classroom("./public/videos", "absinthe", "deadbeef")
    root_path = "./public/videos"
    classrooms = read_classrooms(root_path)
    print(read_classroom_index(root_path, classrooms[0].get("id")))
    add_date_to_classroom(root_path, classrooms[0].get(
        "id"), "2019-12-05", "super sparkle time", ["15:00", "23:00"])
    print(read_classroom_index(root_path, classrooms[0].get("id")))
