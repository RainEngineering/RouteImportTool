# Plant Apps Route Import tool

This script exports routes from one Plant Apps instance and imports them to another

There is a possibility of routes being partially imported if configuration isn't complete on the server regarding data the routes need (For example: route-level property definitions)

This tool works best if routes need to move from one instance to another and both instances have either been cloned or mirrored against each other and other imports have occurred.

## Usage

1. Install Python
2. Clone the repository using Git `git clone git@github.com:RainEngineering/RouteImportTool.git`

- alternatively, you can use whichever method to pull the tool to your computer such as the github desktop app

4. Navigate using terminal/command prompt/powershell to the root of the tool (you should see main.py in your current directoy)
5. install dependencies with PIP in your terminal `pip install -r requirements.txt`
6. Create a copy of `.env.example` and create a new file called `.env` with the same content
7. Enter the values in the new `.env` file
8. Copy and paste your route IDs (separated by newline) into the routes.txt file or any other file on your PC
9. Run the command `python main.py <path>` where `<path>` is the path to the file you just modified in step 8
10. After processing all of the routes, there could be some errors and they will be printed to the screen to let you know which routes failed to auto import. These routes will have to be fixed manually
