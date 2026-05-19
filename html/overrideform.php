<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>

<head>
<meta content="text/html; charset=utf-8" http-equiv="Content-Type">
<title>Untitled 1</title>
	<style type="text/css">
.wrap {
	width:300px;
	margin:0 auto;
	background-color: #ffffff;
	opacity: 0.9;
	border-radius: 25px;
	text-align: center;
}
body {
     background-image: url("/images/greenhousebg4.jpg");
     background-repeat: no-repeat;
     background-position: center top;
	 background-attachment: fixed;
 } 
	</style>
</head>

<body>
<div class="wrap">
<br>
<form action="overrideform2.php" method="post" name="override">
	Window Override<br><select name="windowstatus">
	<option selected="" value="1">Open</option>
	<option value="0">Close</option>
	</select> for <select name="windowoverridetime">
	<option></option>
	<option value="30">0.5</option>
	<option value="60">1</option>
	<option value="90">1.5</option>
	<option value="120">2</option>
	<option value="180">3</option>
	<option value="240">4</option>
	<option value="300">5</option>
	<option value="360">6</option>
	<option value="420">7</option>
	<option value="480">8</option>
	<option value="540">9</option>
	<option value="600">10</option>
	<option value="660">11</option>
	<option value="720">12</option>
	</select> Hours<br><br>
	Fan Override<br><select name="fanstatus">
	<option selected="" value="1">On</option>
	<option value="0">Off</option>
	</select> for <select name="fanoverridetime">
	<option></option>
	<option value="30">0.5</option>
	<option value="60">1</option>
	<option value="90">1.5</option>
	<option value="120">2</option>
	<option value="180">3</option>
	<option value="240">4</option>
	<option value="300">5</option>
	<option value="360">6</option>
	<option value="420">7</option>
	<option value="480">8</option>
	<option value="540">9</option>
	<option value="600">10</option>
	<option value="660">11</option>
	<option value="720">12</option>
	</select> Hours<br><br>
	
	<br><input name="Submit" type="submit" value="Submit"></form>
	<p><a href="index.php">Home</a></p>
<br>
</div>
</body>

</html>
