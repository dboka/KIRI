suppressPackageStartupMessages({
  library(sf)
  library(dplyr)
  library(readr)
  library(sp)
  library(gstat)
})

source("C:/Users/deniss.boka/EUROPEGRID/PIPELINE/pipelineR/uk_elev_contpr.R")

base_dir <- normalizePath(".", winslash = "/", mustWork = TRUE)
project_dir <- normalizePath(file.path(base_dir, ".."), winslash = "/", mustWork = TRUE)
out_root <- file.path(project_dir, "DATA_LAST_60")
manifest_path <- file.path(out_root, "precip_obs", "precip_windows_manifest.csv")
interp_dir <- file.path(out_root, "precip_grids")
metadata_dir <- file.path(out_root, "metadata")
dir.create(interp_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(metadata_dir, recursive = TRUE, showWarnings = FALSE)

grid_csv <- file.path(base_dir, "outputs", "grid_1km_municipalities_centroid.csv")
stations_gpkg <- "C:/Users/deniss.boka/EUROPEGRID/PIPELINE/data/stations_precip_ONLY_PLUS_LT_ELEV_from_grid_2025-06-19.gpkg"

args <- commandArgs(trailingOnly = TRUE)
limit_dates <- NA_integer_
if (length(args) >= 1 && nzchar(args[[1]])) {
  limit_dates <- as.integer(args[[1]])
}

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

if (!file.exists(manifest_path)) {
  stop(paste0("Missing manifest: ", manifest_path, "\nRun prepare_last_60_precip_obs.py first."))
}

manifest <- readr::read_csv(manifest_path, show_col_types = FALSE, locale = readr::locale(encoding = "UTF-8")) %>%
  mutate(
    target_date = as.character(target_date),
    period = as.character(period),
    obs_file = as.character(obs_file)
  )

target_dates <- sort(unique(as.character(manifest$target_date)))
if (!is.na(limit_dates)) {
  target_dates <- head(target_dates, limit_dates)
}

grid_sf <- read_grid_kiri(grid_csv)
grid_attrs <- grid_sf %>% sf::st_drop_geometry()

station_qc <- list()
date_qc <- list()

for (target_day in target_dates) {
  cat("\n==============================\n")
  cat("Target date:", target_day, "\n")
  date_rows <- manifest[as.character(manifest$target_date) == target_day, , drop = FALSE]
  all_preds <- list()

  for (period in c("P30", "P90", "P730")) {
    row <- date_rows[as.character(date_rows$period) == period, , drop = FALSE]
    if (nrow(row) != 1) {
      stop(paste0("Missing manifest row for ", target_day, " ", period))
    }
    obs_path <- row$obs_file[[1]]
    if (!file.exists(obs_path)) {
      stop(paste0("Missing obs file: ", obs_path))
    }

    obs <- readr::read_csv(obs_path, show_col_types = FALSE, locale = readr::locale(encoding = "UTF-8")) %>%
      mutate(
        gh_id = as.character(gh_id),
        value_mm = as.numeric(value_mm)
      ) %>%
      filter(is.finite(value_mm))

    stations_sf <- read_stations_kiri(stations_gpkg, obs)
    if (nrow(stations_sf) < 7) {
      stop(paste0(target_day, " ", period, ": too few stations for interpolation: ", nrow(stations_sf)))
    }

    cat("\n== ", target_day, " ", period, " ==\n", sep = "")
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

    all_preds[[period]] <- pred_values
    station_qc[[paste(target_day, period, sep = "_")]] <- uk$stations_used %>%
      sf::st_drop_geometry() %>%
      transmute(
        target_date = target_day,
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

  out_file <- file.path(interp_dir, paste0("grid_precip_P30_P90_P730_mm_", gsub("-", "_", target_day), ".csv"))
  readr::write_csv(combined, out_file)
  cat("Saved combined grid:", out_file, "\n")

  date_qc[[target_day]] <- tibble::tibble(
    target_date = target_day,
    rows = nrow(combined),
    p30_missing = sum(is.na(combined$P30_mm)),
    p90_missing = sum(is.na(combined$P90_mm)),
    p730_missing = sum(is.na(combined$P730_mm)),
    output_file = out_file
  )
}

station_qc_out <- file.path(interp_dir, "station_precip_windows_used.csv")
readr::write_csv(bind_rows(station_qc), station_qc_out)

date_qc_out <- file.path(metadata_dir, "precip_grid_qc.csv")
readr::write_csv(bind_rows(date_qc), date_qc_out)

cat("\nDONE last-60 precipitation interpolation\n")
cat("Dates:", length(target_dates), "\n")
cat("Grid folder:", interp_dir, "\n")
cat("Station QC:", station_qc_out, "\n")
cat("Date QC:", date_qc_out, "\n")
