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
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Greenhouse Combined Graphs</title>
<link rel="shortcut icon" type="image/x-icon" href="images/greenhouseicon.ico">
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
<body>

<?php
# Calculate and populate time variables for graphs
$mytimenow = time();
$timegroups = array(
  array('Last 2 Hours', $mytimenow - 7200),
  array('Last 4 Hours', $mytimenow - 14400),
  array('Last 12 Hours', $mytimenow - 43200),
  array('Last 24 Hours', $mytimenow - 86400),
  array('Last 7 Days', $mytimenow - 604800)
);

foreach ($timegroups as $index => $timegroup) {
  $title = $timegroup[0];
  $starttime = $timegroup[1];
  $chartid = $index + 1;
?>

<div class="wrapchart" id="chart<?php echo $chartid; ?>">
<p class="largeheader"><br><?php echo $title; ?><br><br>
<img alt="<?php echo $title; ?> Temperature Graph" src="/cacti/graph_image.php?local_graph_id=24&graph_start=<?php echo $starttime; ?>&graph_end=<?php echo $mytimenow; ?>&graph_width=800&graph_height=200"><br>
<img alt="<?php echo $title; ?> Operations Graph" src="/cacti/graph_image.php?local_graph_id=22&graph_start=<?php echo $starttime; ?>&graph_end=<?php echo $mytimenow; ?>&graph_width=800&graph_height=200"><br><br></p>
</div>
<?php
}
?>

<div class="wrap" id="nav">
<table style="width: 300px" align="center">
	<tr>
		<td class="auto-style9" style="width: 199px"><br><a href="index.php"><img alt="Thermometer" height="100" src="images/greenhousehome.png" width="100"><br>Home</a><br><br></td>
		<td class="auto-style9" style="width: 199px"><br><a href="graphs.php"><img alt="Graphs" height="100" src="images/chart01.png" width="100"><br>Graphs</a><br><br></td>
	</tr>
</table>
</div>
</body>
</html>
