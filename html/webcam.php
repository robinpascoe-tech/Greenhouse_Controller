<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<?php
  $bg = array('greenhousebg4.jpg', 'greenhousebg5.jpg', 'greenhousebg6.jpg', 'greenhousebg7.jpg', 'greenhousebg8.jpg', 'greenhousebg9.jpg', 'greenhousebg10.jpg', 'greenhousebg11.jpg', 'greenhousebg12.jpg', 'greenhousebg13.jpg' ); // array of filenames

  $i = rand(0, count($bg)-1); // generate random number size of the array
  $selectedBg = "$bg[$i]"; // set variable equal to which random filename was chosen
?>
<head>
<meta content="en-ca" http-equiv="Content-Language">
<meta content="text/html; charset=utf-8" http-equiv="Content-Type">
<meta http-equiv="refresh" content="60"/>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Greenhouse Webcam</title>
<style type="text/css">
<!--
body{
background: url(images/<?php echo $selectedBg; ?>) no-repeat;
}
-->
</style>
<link rel='stylesheet' type='text/css' href='css/style.css' />
<link id="size-stylesheet" rel='stylesheet' type='text/css' href='css/narrow.css' />
<script type='text/javascript' src='js/resolution-test.js'></script>
</head>
<body>

<div class="wrapwebcam" id="Webcam div">
<h2>Front<br><?php echo "<img  src='/shm/webcam1.jpg?" . filemtime('shm/webcam1.jpg') . "'  />"; ?></h2>
<!-- <img src="/shm/webcam1.jpg"> -->
<h2>Back<br><?php echo "<img  src='/shm/webcam2.jpg?" . filemtime('shm/webcam2.jpg') . "'  />"; ?></h2>
</div>
<div class="wrap" id="nav">
<table style="width: 300px" align="center">
	<tr>
		<td class="auto-style9" style="width: 199px"><br><a href="index.php"><img alt="Thermometer" height="100" src="images/greenhousehome.png" width="100"><br>Home</a><br><br></td>

	</tr>
</table>
</div>
</body>
</html>
