window.onload = function () {
    document.getElementById("canvas_area").style.display = "none"
    document.getElementById("room_area").style.display = "none"
    document.getElementById("result_area").style.display = "none"

    let sock = new WebSocket("wss://pu2msqmfgk.execute-api.ap-northeast-1.amazonaws.com/prod");

    let canvas = new fabric.Canvas('test_canvas');
    canvas.isDrawingMode = true;
    canvas.freeDrawingBrush.color = '#000000';
    canvas.freeDrawingBrush.width = 5;

    let n_time = 30
    let crnt_odai = ""
    let odai_list = undefined
    let img_id = 0


    sock.onmessage = function (event) {
        const data = JSON.parse(event.data)
        console.log(data)
        switch (data["command"]) {
            case "enter_room":
                add_user(data["name"])
                break
            case "game_start":
                document.getElementById("room_area").style.display = "none"
                document.getElementById("canvas_area").style.display = "block"
                first_game_start(data)
                break
            case "predict":
                let element = document.getElementById('list')
                while (element.lastChild) {
                    element.removeChild(element.lastChild);
                }
                for (let i = 0; i < 5; i++) {
                    const liLast = document.createElement('li')
                    liLast.textContent = data["scores"][i]["key"] + ": " + data["scores"][i]["value"]
                    element.appendChild(liLast)
                }
                break
        }
    }

    login.onclick = () => {
        let msg = {
            "action": "enter_room",
            "room_id": room_id.value,
            "user_name": user_name.value
        }
        sock.send(JSON.stringify(msg));
        console.log("login! " + msg["room_id"] + ", " + msg["user_name"])
        document.getElementById("room_area").style.display = "block"
        document.getElementById("login_area").style.display = "none"
    };

    game_start.onclick = () => {
        let msg = {
            "action": "start_game",
            "room_id": room_id.value,
            "n_odai": 6,
            "n_time_sec": 30
        }
        sock.send(JSON.stringify(msg));
    }

    delete_btn.onclick = () => {
        canvas.clear();
    }

    canvas.on("mouse:up", function (option) {
        // ???????????????????????????????????????????????????
        setTimeout(post_img, 1);
    })

    function post_img() {
        let msg = {
            "action": "predict",
            "odai": "???",
            "is_fin": false,
            "img_id": "hoge",
            "img_b64": canvas.toDataURL("image/jpeg")
        }
        sock.send(JSON.stringify(msg));
    }

    function post_img_fin() {
        let msg = {
            "action": "predict",
            "odai": crnt_odai,
            "is_fin": true,
            "img_id": img_id,
            "img_b64": canvas.toDataURL("image/jpeg")
        }
        sock.send(JSON.stringify(msg));
        canvas.clear();
        alert("??????????????????????????? OK???????????????????????????????????????")
        next_game_start()
    }

    function first_game_start(data) {
        let odai_view = document.getElementById("odai")
        odai_view.textContent = "??????: " + data["odai"][0]
        crnt_odai = data["odai"][0]
        odai_list = data["odai"]
        n_time = data["n_time"] * 1000
        setTimeout(post_img_fin, n_time)
    }

    function next_game_start() {
        img_id += 1
        if (img_id == odai_list.length) {
            alert("???????????????")
        }
        else {
            crnt_odai = odai_list[img_id]
            let odai_view = document.getElementById("odai")
            odai_view.textContent = "??????: " + crnt_odai
            setTimeout(post_img_fin, n_time)
        }
    }
}

function add_user(user_name) {

    let root_div = document.createElement("div");
    root_div.classList.add("flex")
    root_div.classList.add("flex-col")
    root_div.classList.add("sm:flex-row")
    root_div.classList.add("items-center")
    root_div.classList.add("gap-2")
    root_div.classList.add("md:gap-4")

    let img_div = document.createElement("div");
    img_div.classList.add("w-24")
    img_div.classList.add("md:w-32")
    img_div.classList.add("h-24")
    img_div.classList.add("md:h-32")
    img_div.classList.add("bg-gray-100")
    img_div.classList.add("rounded-full")
    img_div.classList.add("overflow-hidden")
    img_div.classList.add("shadow-lg")

    let img_src = document.createElement("img");
    img_src.src = Math.floor(Math.random() * 10) + ".png"
    img_src.classList.add("w-full")
    img_src.classList.add("h-full")
    img_src.classList.add("object-cover")
    img_src.classList.add("object-center")

    let user_name_div = document.createElement("div");
    user_name_div.textContent = user_name
    user_name_div.classList.add("text-indigo-500")
    user_name_div.classList.add("md:text-lg")
    user_name_div.classList.add("font-bold")
    user_name_div.classList.add("text-center")
    user_name_div.classList.add("sm:text-left")

    img_div.appendChild(img_src)
    root_div.appendChild(img_div)
    root_div.appendChild(user_name_div)

    let base = document.getElementById("room_area_base")
    base.appendChild(root_div)
}