suppressPackageStartupMessages({
  library(sf)
  library(dplyr)
  library(readr)
  library(sp)
  library(gstat)
})

source("C:/Users/deniss.boka/EUROPEGRID/PIPELINE/pipelineR/uk_elev_contpr.R")

base_dir <- normalizePath(".", winslash = "/", mustWork = TRUE)
precip_dir <- file.path(base_dir, "precip_outputs")
obs_dir <- file.path(precip_dir, "obs")
interp_dir <- file.path(precip_dir, "interpolated")
dir.create(interp_dir, recursive = TRUE, showWarnings = FALSE)

grid_csv <- file.path(base_dir, "outputs", "grid_1km_municipalities_centroid.csv")
stations_gpkg <- "C:/Users/deniss.boka/EUROPEGRID/PIPELINE/data/stations_precip_ONLY_PLUS_LT_ELEV_from_grid_2025-06-19.gpkg"

windows <- tibble::tribble(
  ~period, ~obs_file,
  "P30",  "obs_P30_precip_2026-05-17_2026-06-15.csv",
  "P90",  "obs_P90_precip_2026-03-18_2026-06-15.csv",
  "P730", "obs_P730_precip_2024-06-16_2026-06-15.csv"
)

read_grid_kiri <- function(path) {
  gr <- readr::read_csv(
    path,
    show_col_types = FALSE,
    locale = readr::locale(encoding = "UTF-8"),
    col_types = readr::cols(
      ID = readr::col_character(),
      grid_id = readr::col_character(),
      municipality_code = readr::col_character(),
      municipality_atvk = readr::col_character(),
      municipality_name = readr::col_character(),
      .default = readr::col_guess()
    )
  )

  required <- c("grid_id", "x", "y", "h5", "cont_pr", "municipality_code", "municipality_atvk", "municipality_name")
  missing <- setdiff(required, names(gr))
  if (length(missing) > 0) {
    stop(paste0("Grid CSV missing columns: ", paste(missing, collapse = ", ")))
  }

  gr <- gr %>%
    mutate(
      grid_id = as.character(grid_id),
      x = as.numeric(x),
      y = as.numeric(y),
      h5 = as.numeric(h5),
      cont_pr = as.numeric(cont_pr)
    )

  sf::st_as_sf(gr, coords = c("x", "y"), crs = 3059, remove = FALSE)
}

read_stations_kiri <- function(path, obs_df) {
  stations <- sf::st_read(path, layer = "stations", quiet = TRUE) %>%
    sf::st_transform(3059) %>%
    mutate(GH_ID = as.character(GH_ID))

  obs_ids <- unique(as.character(obs_df$gh_id))
  stations <- stations %>%
    filter(GH_ID %in% obs_ids) %>%
    mutate(
      ELEVATION = as.numeric(ELEVATION),
      cont_pr = as.numeric(cont_pr)
    )

  xy <- sf::st_coordinates(stations)
  stations$x <- as.numeric(xy[, 1])
  stations$y <- as.numeric(xy[, 2])
  stations
}

grid_sf <- read_grid_kiri(grid_csv)
grid_attrs <- grid_sf %>% sf::st_drop_geometry()

all_preds <- list()
station_qc <- list()

for (i in seq_len(nrow(windows))) {
  period <- windows$period[i]
  obs_path <- file.path(obs_dir, windows$obs_file[i])
  if (!file.exists(obs_path)) {
    stop(paste0("Missing obs file for ", period, ": ", obs_path))
  }

  obs <- readr::read_csv(obs_path, show_col_types = FALSE, locale = readr::locale(encoding = "UTF-8")) %>%
    mutate(
      gh_id = as.character(gh_id),
      value_mm = as.numeric(value_mm)
    ) %>%
    filter(is.finite(value_mm))

  stations_sf <- read_stations_kiri(stations_gpkg, obs)
  if (nrow(stations_sf) < 7) {
    stop(paste0(period, ": too few stations for interpolation: ", nrow(stations_sf)))
  }

  cat("\n== ", period, " ==\n", sep = "")
  cat("Obs stations:", nrow(obs), "\n")
  cat("Stations with metadata:", nrow(stations_sf), "\n")

  uk <- uk_interpolate_elev_contpr(
    stations_sf = stations_sf,
    grid_sf = grid_sf,
    obs_df = obs,
    vgm_model = "Exp",
    range_m = 45000,
    nugget = 0,
    grid_elev_col = "h5",
    grid_cont_col = "cont_pr",
    station_cont_col = "cont_pr"
  )

  pred_sf <- sf::st_as_sf(uk$grid_pred_sp)
  pred_values <- pred_sf %>%
    sf::st_drop_geometry() %>%
    transmute(grid_id = grid_attrs$grid_id, !!paste0(period, "_mm") := round(as.numeric(var1.pred), 3))

  out_period_csv <- file.path(interp_dir, paste0("grid_precip_", period, "_mm.csv"))
  readr::write_csv(pred_values, out_period_csv)
  cat("Saved:", out_period_csv, "\n")

  all_preds[[period]] <- pred_values
  station_qc[[period]] <- uk$stations_used %>%
    sf::st_drop_geometry() %>%
    transmute(
      period = period,
      gh_id = as.character(GH_ID),
      station = if ("Station" %in% names(.)) as.character(Station) else NA_character_,
      value_mm = as.numeric(value),
      elevation = as.numeric(ELEVATION),
      cont_pr = as.numeric(cont_pr)
    )
}

combined <- grid_attrs %>%
  transmute(
    grid_id = as.character(grid_id),
    x = as.numeric(x),
    y = as.numeric(y),
    lon = as.numeric(lon),
    lat = as.numeric(lat),
    municipality_code = as.character(municipality_code),
    municipality_atvk = as.character(municipality_atvk),
    municipality_name = as.character(municipality_name)
  )

for (period in names(all_preds)) {
  combined <- combined %>% left_join(all_preds[[period]], by = "grid_id")
}

combined_out <- file.path(interp_dir, "grid_precip_P30_P90_P730_mm.csv")
readr::write_csv(combined, combined_out)

station_qc_out <- file.path(interp_dir, "station_precip_windows_used.csv")
readr::write_csv(bind_rows(station_qc), station_qc_out)

cat("\nDONE precipitation interpolation\n")
cat("Combined grid:", combined_out, "\n")
cat("Station QC:", station_qc_out, "\n")
